# Profiler
A Python script to check wireless (802.11) capabilities based on association request frame contents. It has been developed to be specifically used with the WLAN Pi platform. 

The script performs two functions:

- Create a "fake" access point that will broadcast an SSID of your choosing
- As clients attempt to join the SSID broadcast by the fake AP, it will analyze the association frames generated by clients to determine their 802.11 capabilities.

Understanding client capabilities is an important aspect of Wireless LAN design. It helps a network designer understand the features that may enabled on a WLAN to optimize the design.

The capabilities supported by each client type may vary enourmously, depending on factors such as the client wirelss chipset, number of antennas, age of the client etc. Each client supplies details of its capabilities as it sends an 802.11 association frame to an access point. By capturing this frame, it is possible to decode and report on the client capabilities. On caveat, however, is that the client will match the capabilites advertised by an access point. For instance, if a 3 stream client detects that the acces point support only 2 streams, it will report that it (the client) only support 2 streams also. 

To get around this shortcoming, this script uses the Python FakeAP module to create a fake AP that advertises that it has the hightest levels of feature set enabled. This fools the client in to revealing its full capabilities, which are then analyzed from the association frame that it uses as it attempts to join the fake AP. It then uses the Scapy module to capture and  analyze the association framse from each client to determie its capabilities.

A textual report is dumped in realtime to stdout and a text file copy is also dumped in to a directory of the WLANPi web directory to allow browsing of reports. In addition, a copy of the association frame is dumped in PCAP file format in to web directory. Each reault is also added to a summary CSV report file that is created for each session when the script is run.

Report files are dumped in the following web directories for browsing:

- http://<wlanpi_ip_address>/profiler/clients (on directory per client, with PCAP and text capabuility report dumped in the directory)
- http://<wlanpi_ip_address>/profiler/reports (contains a CSV report of all clients for each session when the script is run)

## Using the Script
To use the script on the WLANPi:

- Open an SSH session to the WLANPi using the 'wlanpi' username, login and create a new directory using the command : mkdir profiler
- Change directory to the newly created directory: cd ./profiler
- Transfer the profiler.py script to the WLANPi (e.g. using SFTP)
- Make the script executable with "chmod a+x profiler.py"
- Ensure that a USB wireless adapter that support monitor mode (e.g. Comfast CF-912AC) is plugged in to the WLANPi
- Run the script using the command : ./profiler.py -c 36 -s "My_SSID" (enter the root password when prompted)

The script will run continuously, listening for association requests and analyzing the client capabilites in realtime. To end the script, hit "Ctrl-c". Leave the script running while testing clients.

To trigger client profiling:

- Fire up the client(s) to test
- Search for the SSID configured on the fake AP
- Attempt to join the fake AP SSID from the test client
- When prompted, enter a random PSK on the client under test (any string of 8 or more characters will do)
- After a few seconds, a textual report will (hopefully) be displayed in SSH session already established to the WLAN Pi as it tries to associate. Note the client will not join the fake AP SSID.
- Once clients have been tested and successfully triggered a client report, the captured association frame is dumped in to a PCAP file (browse to "http://<ip_address_of_wlanpi>/profiler" to see PCAP dumps and text reports)

## Usage

```
Usage:
    profiler.py")
    profiler.py [ -c <channel num> ] [ -s "SSID Name" ] [ -i interface_name ] [ --no11r ]
    profiler.py -h
    profiler.py -v
    profiler.py --help
    profiler.py --clean  (Clean out old CSV reports)
    
Command line options:

        -h       Shows help
        -c       Sets channel for fake AP
        -s       Sets name of fake AP SSID
        -i       Sets name of fake AP wireless interface on WLANPi
       --no11r   Disables 802.111r information elements
 
 ```
### Examples:

```
# capture frames on channel 48 using the default SSID
wlanpi@wlanpi:/home/wlanpi/profiler# sudo python ./profiler.py -c 48

```

```
# capture frames on channel 36 using an SSID called 'JOIN ME'
wlanpi@wlanpi:/home/wlanpi/profiler# sudo python ./profiler.py -c 36 -s "JOIN ME"

```

```
# capture frames on channel 100 using an SSID called 'Profiler' with 802.11r disabled for clients that don't like 11r
wlanpi@wlanpi:/home/wlanpi/profiler# sudo python ./profiler.py -c 100 -s "Profiler" --no11r
```

## Screenshot

![Screenshot](https://github.com/WLAN-Pi/Profiler/blob/master/screenshot1.png)

## Caveats
- Note that this is work in progress and is not guaranteed to report accurate info (despite our best efforts). **You have been warned**
- A client will generally only report the capabilities it has that match the network it associates to. If you want the client to report all of its capabilities, it **must** be associating with a network that supports those capabilities (e,g, a 3 stream client will not report it supports 3 streams if the AP is asscoiates with supports only one stream). The fake AP in this script attempts to provide a simulate a fully featured AP, but this is obviously a sumulated AP, so there may be cases when it does not behave as expected. 
- Reporting of 802.11k capabilities is very poor among clients I have tested - treat with extreme caution (check for neighbor report requests from a WLC/AP debug to be sure)

## Credits
This project is a spin-off of the wlan-client=capability project. Full details of the previous project can be found at: [https://github.com/wifinigel/wlan-client-capability]

