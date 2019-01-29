#!/usr/bin/python

########################################################################
# define fake AP parameters
CHANNEL = 36
SSID = 'Client Capabilties'
INTERFACE = 'wlan0'
#
# !!!!!!!!!!!!!! Do Not Touch Anything Below Here (Please) !!!!!!!!!!!!
#
########################################################################

#import libraries
from fakeap import *
from fakeap.constants import *

from scapy.all import *
from scapy.layers.dot11 import *

import subprocess
from types import MethodType
import sys
import os
import time
import csv
import getopt

__author__ = 'Jerry Ola, Nigel Bowden'
__version__ = '0.1'
__email__ = 'wlanpi@gmail.com'
__status__ = 'beta'

# we must be root to run this script - exit with msg if not
if not os.geteuid()==0:
    print("\n#####################################################################################")
    print("You must be root to run this script (use 'sudo wlan_client_capability.py') - exiting" )
    print("#####################################################################################\n")
    sys.exit()

################################
# Set up working directories
################################

# Report & file dump directories
DIRS = {
    'dump_dir': '/var/www/html/profiler', # reporting root dir
    'clients_dir': '/var/www/html/profiler/clients', # client data dir
    'reports_dir': '/var/www/html/profiler/reports', # reports dir
}

# check if each dir exists, create if not
for dir_key in ['dump_dir', 'clients_dir', 'reports_dir']:
    dest_dir = DIRS[dir_key]
   
    if not os.path.isdir(dest_dir):
        try:
            os.mkdir(dest_dir)
        except Exception as ex:
            print("Trying to create directory: {} but having an issue: {}".format(dest_dir, ex))
            print("Exiting...")
            sys.exit()

# figure out the dest address for this SSH session
netstat_output = subprocess.check_output("netstat -tnpa | grep 'ESTABLISHED.*sshd'", shell=True)
dest_ip_re = re.search('(\d+?\.\d+?\.\d+?\.\d+?)\:22', netstat_output)

if dest_ip_re is None:
    SSH_DEST_IP = False
else:            
    SSH_DEST_IP = dest_ip_re.group(1)

######################################
#  assoc req frame tag list numbers
######################################

# power information
POWER_MIN_MAX_TAG = "33"

# channels supported by client
SUPPORTED_CHANNELS_TAG = "36"

# 802.11n support info
HT_CAPABILITIES_TAG    = "45"

# 802.11r support info
FT_CAPABILITIES_TAG    = "54"

# 802.11k support info
RM_CAPABILITIES_TAG    = "70"

# 802.11v
EXT_CAPABILITIES_TAG   = "127"

# 802.11ac support info
VHT_CAPABILITIES_TAG   = "191"

# list of detected clients
detected_clients = []

# get our start time for csv timestamp
time_now = time.strftime("%Y-%m-%d-%H-%M-%S")

# build csv filename
csv_file = DIRS['reports_dir'] + '/db-' + time_now + '.csv'

##################
# Functions
##################

def analyze_frame_cb(self, packet, silent_mode=False):

        analyze_frame(packet, silent_mode)

def analyze_frame(packet, silent_mode=False):
  
    # pull off the RadioTap, Dot11 & Dot11AssoReq layers
    dot11 = packet.payload
    frame_src_addr = dot11.addr2
    
    if frame_src_addr in detected_clients:
        
        # already analysed this client, moving on
        print("Detected " + str(frame_src_addr) + " again, ignoring..." )
        return(False)
    
    # add client to detected clients list
    detected_clients.append(frame_src_addr)
    
    # get mac address in dashed format to use later
    mac_addr = frame_src_addr.replace(':', '-', 5)
    
    # create a dir to dump client data into
    client_dir = DIRS['clients_dir'] + '/' + mac_addr
    
    if not os.path.isdir(client_dir):
        try:
            os.mkdir(client_dir)
        except Exception as ex:
            print("Trying to create directory: {} but having an issue: {}".format(client_dir, ex))
            print("Exiting...")
            sys.exit()
        
    # dump out the frame to a file
    dump_filename = client_dir + '/' + mac_addr + '.pcap'
    wrpcap(dump_filename, [packet])  
    
    capabilites = dot11.getfieldval("cap")
    dot11_assoreq = dot11.payload.payload
    dot11_elt = dot11_assoreq

    # common dictionary to store all tag lists
    dot11_elt_dict = {}

    # analyse the 802.11 frame tag lists & store in a dictionary
    while dot11_elt:

        # get tag number
        dot11_elt_id = str(dot11_elt.ID)

        # get tag list
        dot11_elt_info = dot11_elt.getfieldval("info")
        
        # covert tag list in to useable format (decimal list of values)
        dec_array = map(ord, str(dot11_elt_info))
        #hex_array = map(hex, dec_array)

        # store each tag list in a common tag dictionary
        dot11_elt_dict[dot11_elt_id] = dec_array
        
        # move to next layer - end of while loop
        dot11_elt = dot11_elt.payload
    
    # dictionary to store capabilities as we decode them
    capability_dict = {}
    
    # check if 11n supported
    if HT_CAPABILITIES_TAG in dot11_elt_dict.keys():
        capability_dict['802.11n'] = 'Supported'
        
        spatial_streams = 0
        
        # mcs octets 1 - 4 indicate # streams supported (up to 4 streams only)
        for mcs_octet in range(3, 7):
        
            mcs_octet_value = dot11_elt_dict[HT_CAPABILITIES_TAG][mcs_octet]
        
            if (mcs_octet_value & 255):
                spatial_streams += 1
        
        capability_dict['802.11n'] = 'Supported (' + str(spatial_streams) + 'ss)'
    else:
        capability_dict['802.11n'] = 'Not reported*'
        
    # check if 11ac supported
    if VHT_CAPABILITIES_TAG in dot11_elt_dict.keys():
        
        # Check for number streams supported
        mcs_upper_octet = dot11_elt_dict[VHT_CAPABILITIES_TAG][5]
        mcs_lower_octet = dot11_elt_dict[VHT_CAPABILITIES_TAG][4]
        mcs_rx_map = (mcs_upper_octet * 256) + mcs_lower_octet
        
        # define the bit pair we need to look at
        spatial_streams = 0
        stream_mask = 3

        # move through each bit pair & test for '10' (stream supported)
        for mcs_bits in range(1,9):
                    
            if (mcs_rx_map & stream_mask) != stream_mask:
            
                # stream mask bits both '1' when mcs map range not supported
                spatial_streams += 1
            
            # shift to next mcs range bit pair (stream)
            stream_mask = stream_mask * 4
        
        vht_support = 'Supported (' + str(spatial_streams) + 'ss)'
        
        # check for SU & MU beam formee support
        mu_octet = dot11_elt_dict[VHT_CAPABILITIES_TAG][2]
        su_octet = dot11_elt_dict[VHT_CAPABILITIES_TAG][1]
        
        beam_form_mask = 8
        
        # bit 4 indicates support for both octets (1 = supported, 0 = not supported) 
        if (su_octet & beam_form_mask):
            vht_support += ", SU BF supported"
        else:
            vht_support += ", SU BF not supported"
         
        if (mu_octet & beam_form_mask):
            vht_support += ", MU BF supported"
        else:
            vht_support += ", MU BF not supported"
        
        capability_dict['802.11ac'] = vht_support

    else:
        capability_dict['802.11ac'] = 'Not reported*'
        
    # check if 11k supported
    if RM_CAPABILITIES_TAG in dot11_elt_dict.keys():
        capability_dict['802.11k'] = 'Supported'
    else:
        capability_dict['802.11k'] = 'Not reported* - treat with caution, many clients lie about this'

    # check if 11r supported
    if FT_CAPABILITIES_TAG in dot11_elt_dict.keys():
        capability_dict['802.11r'] = 'Supported'
    else:
        capability_dict['802.11r'] = 'Not reported*'

    # check if 11v supported
    capability_dict['802.11v'] = 'Not reported*'
    
    if EXT_CAPABILITIES_TAG in dot11_elt_dict.keys():
    
        ext_cap_list = dot11_elt_dict[EXT_CAPABILITIES_TAG]
    
        # check octet 3 exists
        if 3 <= len(ext_cap_list):

            # bit 4 of octet 3 in the extended capabilites field
            octet3 = ext_cap_list[2]
            bss_trans_support = int('00001000', 2)
            
            # 'And' octet 3 to test for bss transition support
            if octet3 & bss_trans_support:
                capability_dict['802.11v'] = 'Supported'
    
    # check if power capabilites supported
    capability_dict['Max_Power'] = 'Not reported'
    capability_dict['Min_Power'] = 'Not reported'
    
    if POWER_MIN_MAX_TAG in dot11_elt_dict.keys():

        # octet 3 of power capabilites
        max_power = dot11_elt_dict[POWER_MIN_MAX_TAG][1]
        min_power = dot11_elt_dict[POWER_MIN_MAX_TAG][0]
        
        capability_dict['Max_Power'] = str(max_power) + " dBm"
        capability_dict['Min_Power'] = str(min_power) + " dBm"

    # check supported channels
    if SUPPORTED_CHANNELS_TAG in dot11_elt_dict.keys():
        channel_sets_list = dot11_elt_dict[SUPPORTED_CHANNELS_TAG]
        channel_list = []
        
        while (channel_sets_list):
        
            start_channel = channel_sets_list.pop(0)
            channel_range = channel_sets_list.pop(0)
            
            # check for if 2.4Ghz or 5GHz
            if start_channel > 14:
                channel_multiplier = 4
            else:
                channel_multiplier = 1
                
            
            for i in range(channel_range):
                channel_list.append(start_channel + (i * channel_multiplier))
        
        capability_dict['Supported_Channels'] = ', '.join(map(str, channel_list))
        
    else:
        capability_dict['Supported_Channels'] =  "Not reported"
    
    # print our report to stdout
    text_report(frame_src_addr, capability_dict, mac_addr, client_dir, csv_file)
    
    return True

def text_report(frame_src_addr, capability_dict, mac_addr, client_dir, csv_file):

    report_text = ''

    # start report
    report_text += '\n'
    report_text += '-' * 60
    report_text += "\nClient capabilites report - Client MAC: " + frame_src_addr + "\n"
    report_text += '-' * 60
    report_text += '\n'
    
    # print out capabilities (in nice format)
    capabilities = ['802.11k', '802.11r', '802.11v', '802.11n', '802.11ac', 'Max_Power', 'Min_Power', 'Supported_Channels']
    for key in capabilities:
        report_text += "{:<20} {:<20}".format(key, capability_dict[key]) + "\n"
    
    report_text += "\n\n" + "* Reported client capabilities are dependant on these features being available from the wireless network at time of client association\n\n"
    
    print(report_text)
    
    # print results URL
    global SSH_DEST_IP
    
    if SSH_DEST_IP:
        print("[View PCAP & Client Report : http://{}/profiler/clients/{} ]\n".format(SSH_DEST_IP, mac_addr))
    
    # dump out the text to a file
    dump_filename = client_dir + '/' + mac_addr + '.txt'
    
    try:
        f = open(dump_filename, 'w')
        f.write(report_text)
        f.close()
    except Exception as ex:
        print("Error creating file to dump client info ({}):".format(dump_filename))
        print(ex)
        sys.exit()
    
    # Check if csv file exists
    if not os.path.exists(csv_file):
    
        # create file with csv headers
        with open(csv_file, mode='w') as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=['Client_Mac'] + capabilities)
            writer.writeheader()
  
    # append data to csv file
    with open(csv_file, mode='a') as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=['Client_Mac'] + capabilities)
        writer.writerow({
            'Client_Mac': frame_src_addr,
            '802.11k': capability_dict['802.11k'],
            '802.11r': capability_dict['802.11r'],
            '802.11v': capability_dict['802.11v'],
            '802.11n': capability_dict['802.11n'],
            '802.11ac': capability_dict['802.11ac'],
            'Max_Power': capability_dict['Max_Power'],
            'Min_Power': capability_dict['Min_Power'],
            'Supported_Channels': capability_dict['Supported_Channels']
        })
  
    return True

def get_ie(ap_channel, ap_ssid, ft=True):

    #Added Information element tags here
    p=    Dot11Elt(ID='SSID', info=ap_ssid) #SSID
    p=p / Dot11Elt(ID='Rates', info="\x8c\x12\x98\x24\xb0\x48\x60\x6c") #Supported Data Rates
    p=p / Dot11Elt(ID=0x46, info="\x02\x00\x00\x00\x00") #RM Enabled Capabilties
    if ft:
        p=p / Dot11Elt(ID=0x36, info="\x45\xc2\x00") #Mobility Domain(802.11r/FT enabled)
        p=p / Dot11Elt(ID=0x30, info="\x01\x00\x00\x0f\xac\x04\x01\x00\x00\x0f\xac\x04\x02\x00\x00\x0f\xac\x02\x00\x0f\xac\x04\x0c\x00") #RSN FT Enabled
    else:
        p=p / Dot11Elt(ID=0x30, info="\x01\x00\x00\x0f\xac\x04\x01\x00\x00\x0f\xac\x04\x01\x00\x00\x0f\xac\x02\x00\x00") #RSN FT disabled
   
    p=p / Dot11Elt(ID=0xdd, info="\x00\x50\xf2\x02\x01\x01\x8a\x00\x03\xa4\x00\x00\x27\xa4\x00\x00\x42\x43\x5e\x00\x62\x32\x2f\x00") #Vendor specific MS corp. WMM/WME:parameter element
    p=p / Dot11Elt(ID=0x2d, info="\xef\x19\x1b\xff\xff\xff\x00\x00\x00\x00\x00\x00\x00\x00\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00") #HT Capabilities
    p=p / Dot11Elt(ID=0x3d, info=chr(ap_channel) + "\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00") #HT Information
    p=p / Dot11Elt(ID=0x7f, info="\x00\x00\x08\x00\x00\x00\x00\x40") #Extended Capatibilities
    p=p / Dot11Elt(ID=0xbf, info="\x32\x00\x80\x03\xaa\xff\x00\x00\xaa\xff\x00\x00") #VHT Capabilties
    p=p / Dot11Elt(ID=0xc0, info="\x00\x24\x00\x00\x00") #VHT Operation
    p=p / Dot11Elt(ID=0xff, info="\x23\x09\x01\x00\x02\x40\x00\x04\x70\x0c\x80\x02\x03\x80\x04\x00\x00\x00\xaa\xff\xaa\xff\x7b\x1c\xc7\x71\x1c\xc7\x71\x1c\xc7\x71\x1c\xc7\x71") # HE Capabilties
    p=p / Dot11Elt(ID=0xff, info="\x24\xf4\x3f\x00\x19\xfc\xff") #HE Operation
    return p

def my_dot11_probe_resp(self, source, ssid):
    # Create probe response packet
    probe_response_packet = self.ap.get_radiotap_header() \
        / Dot11(subtype=5, addr1=source, addr2=self.ap.mac, addr3=self.ap.mac, SC=self.ap.next_sc()) \
        / Dot11ProbeResp(timestamp=self.ap.current_timestamp(), beacon_interval=0x0064, cap=0x1111) \

    #Update information elements
    ft = self.ap.ft
    probe_response_packet = probe_response_packet /get_ie(self.ap.channel, ssid, ft)

    #Send probe response
    self.ap.s2.send(probe_response_packet)

def my_dot11_beacon(self, ssid):
    # Create beacon packet
    beacon_packet = self.ap.get_radiotap_header() \
        / Dot11(subtype=8, addr1='ff:ff:ff:ff:ff:ff', addr2=self.ap.mac, addr3=self.ap.mac) \
        / Dot11Beacon(beacon_interval=0x0064, cap=0x1111) \
        / Dot11Elt(ID='TIM', info="\x05\x04\x00\x03\x00\x00") \

    #Update information elements
    ft = self.ap.ft
    beacon_packet = beacon_packet / get_ie(self.ap.channel, ssid, ft)

    # Update sequence number
    beacon_packet.SC = self.ap.next_sc()

    # Update timestamp
    beacon_packet[Dot11Beacon].timestamp = self.ap.current_timestamp()

    # Send beacon
    self.ap.s1.send(beacon_packet)

def run_fakeap(ap_interface, ap_ssid, ap_channel, ft):

    ap = FakeAccessPoint(ap_interface, ap_ssid)
    ap.wpa = AP_WLAN_TYPE_WPA2  # Enable WPA2

    my_callbacks = Callbacks(ap)

    my_callbacks.cb_recv_pkt = MethodType(my_recv_pkt, my_callbacks)
    my_callbacks.cb_analyze_frame = MethodType(analyze_frame_cb, my_callbacks)

    my_callbacks.cb_dot11_beacon      = MethodType(my_dot11_beacon     , my_callbacks)
    my_callbacks.cb_dot11_probe_req   = MethodType(my_dot11_probe_resp , my_callbacks)

    ap.callbacks = my_callbacks
    
    # signal whether to use ft IE or not
    ap.ft = ft

    # set fake AP channel
    ap.channel = ap_channel
    
    # lower the beacon interval used to account for execution time of script
    ap.beaconTransmitter.interval = 0.015
    ap.run()

def run_msg(ap_interface, ap_ssid, ap_channel):

    global SSH_DEST_IP

    print("\n" + "-" * 44)
    print("Fake AP Starting... \n")
    print("SSID:{} ".format(ap_ssid))
    print("PSK: it doesn't matter :)")
    print("Channel: {}".format(ap_channel))
    print("Interface: {}".format(ap_interface))
    if SSH_DEST_IP:
        print("Results: http://{}/profiler/".format(SSH_DEST_IP))
    print("-" * 44)
    print("\n####################################################################################################")
    print("Connect a Wi-Fi client to SSID:",ap_ssid, "enter anything for a PSK")
    print("we don't actually need the device to connect, we only need the client to send an association request")
    print("####################################################################################################\n")



def my_recv_pkt(self, packet):  # We override recv_pkt to include a trigger for our callback

    if packet.haslayer(Dot11AssoReq):
        self.cb_analyze_frame(packet) 
    self.recv_pkt(packet)


def usage():

    print("\nProfiler verison : {}".format(__version__))
    print("\n Usage:\n")
    print("    profiler.py")
    print('    profiler.py [ -c <channel num> ] [ -s "SSID Name" ] [ -i interface_name ] [ --no11r ]')
    print("    profiler.py -h")
    print("    profiler.py -v")
    print("    profiler.py --help")
    print("    profiler.py --clean  (Clean out old CSV reports)")
    print ("\n Command line options:\n")
    print("    -h       Shows help")
    print("    -c       Sets channel for fake AP")
    print("    -s       Sets name of fake AP SSID")
    print("    -i       Sets name of fake AP wireless interface on WLANPi")
    print("    -h       Prints help page")
    print("   --no11r   Disables 802.111r information elements")
    print("   --help    Prints help page")
    print("   --clean   Cleans out all CSV report files\n\n")
    sys.exit()

def report_cleanup():

    global DIRS
    
    reports_dir = DIRS['reports_dir']
    
    for file in os.listdir(reports_dir):
    
        try:
            print("Removing old file: " + file)
            os.unlink(reports_dir + "/" + file)
        except Exception as ex:
            print("Issue removing file:" + str(ex))
 
    sys.exit()

def main():

    ##########################
    # Process CLI parameters
    ##########################
    
    ap_interface = INTERFACE 
    ap_ssid = SSID
    ap_channel = CHANNEL
    
    ft = True
    
    # Default action run fakeap & analyze assoc req frames
    if len(sys.argv) < 2:
        # fall through to run ap with default parameters
        pass
        
    # Process CLI parameters if we have any
    elif len(sys.argv) >= 2:    
   
        try:
            opts, args = getopt.getopt(sys.argv[1:],'c:s:i:hv', ['no11r', 'clean', 'help'])
        except getopt.GetoptError:
            print("\nOops...syntaxt error, please re-check: \n")
            usage()
        
        for opt, arg in opts:
            if opt == '-h':
                usage()
            elif opt == ("--help"):
                usage()
            elif opt == ("-v"):
                print("\nProfiler version: {}\n".format(__version__))
                sys.exit()
            elif opt == ("--clean"):
                report_cleanup()
            elif opt in ("-c"):
                ap_channel = int(arg)
            elif opt in ("-s"):
                ap_ssid = str(arg)
            elif opt in ("-i"):
                ap_interface = str(arg)
            elif opt in ("--no11r"):
                ft = False

    else:
        usage()
    
    ##########################
    # set up the WLAN adapter
    ##########################

    if_cmds = [
        'ifconfig {} down'.format(ap_interface),
        'iwconfig {} mode monitor'.format(ap_interface),
        'ifconfig {} up'.format(ap_interface),
        'iw {} set channel '.format(ap_interface) + str(ap_channel)
    ]

    # run WLAN adapter setup commands & check for failures
    for cmd in if_cmds:
        try:            
            subprocess.check_output(cmd + " 2>&1", shell=True)
        except Exception as ex:
            print("Error setting wlan interface config:")
            print(ex)
            sys.exit()

    # run the fakeap
    run_msg(ap_interface, ap_ssid, ap_channel)
    run_fakeap(ap_interface, ap_ssid, ap_channel, ft)
    
       
if __name__ == "__main__":
    main()