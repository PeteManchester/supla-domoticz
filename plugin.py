"""
<plugin key="supla" name="Supla" author="Supla Team" version="0.1.1" externallink="https://supla.org/">
    <description>
        <h2>Supla Plugin</h2>
        <p>
            Building automation systems available on the market are usually very complex, closed and expensive. In many cases they
            must be installed on the very early stages of house construction. SUPLA is simple, open and free of charge. It gives an
            opportunity to build elements based on RaspberryPI, Arduino or ESP8266 platforms and then join them either through LAN
            or WiFi. Through SUPLA you can, among others, control the lighting, switch on and off household appliances and media,
            open and shut gates and doors, or control room temperature. All the above can be done with just touch of a finger. SUPLA
            is available from any place on Earth if you just have a smartphone or tables available as well as Internet access. SUPLA
            is developed based on an Open Software and Open Hardware. This way, you can also develop this project! - <a href="https://www.supla.org/en/">supla.org</a>
        </p>
        <h3>Supla Cloud</h3>
        <p>
            SUPLA-CLOUD is a central point joining the executive devices for indirect and direct operation of your household or
            office appliances and other elements with client applications which you can install on your tablets and smartphones.
            This software allows to operate, from one spot, the whole system infrastructure using any modern Internet browser. Server
            access is free of charge. You can also set up your own independent server working within the Internet or home network
            using system sources which you can download from GITHUB. - <a href="https://www.supla.org/en/">supla.org</a></p>
        <h3>Supported Devices</h3>
        <ul style="list-style-type:square">
            <li>Switches &amp; lights</li>
        </ul>
        <h3>Configuration</h3>
        <ul style="list-style-type:square">
            <li>oAuth Token - Supla Cloud token; for how to obtain it visit <a href="https://github.com/SUPLA/openhab2-addons/tree/master/bundles/org.openhab.binding.supla#generating-token">this link</a>.</li>
            <li>Refresh Time (sec) - time how often plugin should refresh devices state with Supla Cloud</li>
        </ul>
    </description>
    <params>
        <param field="Mode1" label="oAuth Token" required="true"/>
        <param field="Mode2" label="Refresh Time (sec)" required="true" default="30"/>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic+Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections+Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
import datetime
import threading
import Domoticz

from supla_api import *


def build_domoticz_device(channel, device):
    channel_type = channel["function"]["name"]
    #info("ChannelType: " + str(channel_type));
    channel_name = channel["caption"]
    if not channel_name:
        channel_name = device["name"] + "#" + str(channel["id"])
    #unit = len(Devices) + 1
    device_id = str(channel["id"])
    # Get unit number, if any
    unitTest = getUnit(device_id)
    # If it's not in Domoticz already
    if unitTest != 0:
	    #info("Devices has already been added: " + str(device_id))
	    return
    unit = nextUnit()
    if channel_type == "POWERSWITCH" or channel_type == "LIGHTSWITCH":
        info("Creating switch device '" + channel_name + "'" + "  " + str(channel))
        Domoticz.Device(Name=channel_name,
                        TypeName="Switch",
                        Unit=unit,
                        DeviceID=device_id).Create()
    
    if channel_type == "DIMMER":
        info("Creating Dimmer device '" + channel_name + "'" + "  " + str(channel) + " Unit: " + str(unit) )
        Domoticz.Device(Name=channel_name, TypeName="Switch", Unit=unit, Type=241, Subtype=3, Switchtype=7, DeviceID=device_id).Create()        


def update_devices(self):
    #info("Update Devices Start")
    for unit in list(Devices.keys()):   
        device = Devices[unit]
        channel_id = device.DeviceID
        channel =self.api_client.find_channel(channel_id)
        update_device(channel, unit)

def update_device(channel, unit):
    channel_type = channel["function"]["name"]
    #info("update_device: " + str(channel))
    if channel_type == "POWERSWITCH" or channel_type == "LIGHTSWITCH":
        if channel["state"]["on"]:
            n_val = 1
            s_val = "1"          
        else:
            n_val = 0
            s_val = "0"
        info("Changing channel {}/{} to state {}".format(channel["id"], channel_type, s_val))
        Devices[unit].Update(nValue=n_val, sValue=s_val)
    if channel_type == "DIMMER":
        if channel["state"]["on"]:
            Level = channel["state"]["brightness"]
            info("Channel Brightness: " + str(Level))
            UpdateDevice(unit, 1 if Devices[unit].Type == 241 else 2, str(Level), Devices[unit].TimedOut)
        else:
            info("Dimmer is OFF")
            UpdateDevice(unit, 0, 'Off', Devices[unit].TimedOut)
    

def UpdateDevice(Unit, nValue, sValue, TimedOut):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if (Unit in Devices):
        if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue) or (Devices[Unit].TimedOut != TimedOut):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue), TimedOut=TimedOut)
            Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+") TimedOut="+str(TimedOut))
    return

class BasePlugin:
    enabled = False

    def __init__(self):
        self.token = "TOKEN UNKNOWN"
        self.refresh_time = 10
        self.last_refresh = datetime.datetime.now()
        self.api_client = None

    def onStart(self):
        """
        Called when the hardware is started, either after Domoticz start, hardware creation or update
        """
        #Domoticz.Debugging(-1)
        info("onStart called"
              + " | OAuth Token " + Parameters["Mode1"]
              + " | Refresh Time=" + Parameters["Mode2"])
        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
            DumpConfigToLog()
        self.token = Parameters["Mode1"]
        self.refresh_time = int(Parameters["Mode2"])
        self.api_client = supla_api.ApiClient(self.token, lambda msg: debug(msg), lambda msg: error(msg))
        self.create_devices()
        self.onHeartbeat(force=True)

    def create_devices(self):
        #info("Create Devices")
        all_devices = self.api_client.find_all_devices()
        #info("Create Devices: " + str(all_devices))
        for device in all_devices:
            for channel in device["channels"]:
                build_domoticz_device(channel, device)
        

    def onStop(self):
        """
        Called when the hardware is stopped or deleted from Domoticz.
        """
        debug("onStop called")

    def onConnect(self, Connection, Status, Description):
        """
        Called when connection to remote device either succeeds or fails, or when a connection is made to a listening
        Address:Port. Connection is the Domoticz Connection object associated with the event. Zero Status indicates
        success. If Status is not zero then the Description will describe the failure.

        This callback is not called for connectionless Transports such as UDP/IP.
        """
        debug("onConnect called")

    def onMessage(self, Connection, Data):
        """
        Called when a single, complete message is received from the external hardware (as defined by the Protocol
        setting). This callback should be used to interpret messages from the device and set the related Domoticz
        devices as required.

        Connection is the Domoticz Connection object associated with the event.

        Data is normally a ByteArray except where the Protocol for the Connection has structure (such as HTTP or ICMP),
        in that case Data will be a Dictionary containing Protocol specific details such as Status and Headers.
        """
        debug("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        """
        Called when a command is received from Domoticz. The Unit parameters matches the Unit specified in the device
        definition and should be used to map commands to Domoticz devices. Level is normally an integer but may be a
        floating point number if the Unit is linked to a thermostat device. This callback should be used to send
        Domoticz commands to the external hardware. The Color parameter is valid if Command is "Set Color" and is a
        JSON serialized Domoticz color object.

        Domoticz color format:
        ColorMode {
            ColorModeNone = 0,   // Illegal
            ColorModeWhite = 1,  // White. Valid fields: none
            ColorModeTemp = 2,   // White with color temperature. Valid fields: t
            ColorModeRGB = 3,    // Color. Valid fields: r, g, b.
            ColorModeCustom = 4, // Custom (color + white). Valid fields: r, g, b, cw, ww, depending on device capabilities
            ColorModeLast = ColorModeCustom,
        };

        Color {
            ColorMode m;
            uint8_t t;     // Range:0..255, Color temperature (warm / cold ratio, 0 is coldest, 255 is warmest)
            uint8_t r;     // Range:0..255, Red level
            uint8_t g;     // Range:0..255, Green level
            uint8_t b;     // Range:0..255, Blue level
            uint8_t cw;    // Range:0..255, Cold white level
            uint8_t ww;    // Range:0..255, Warm white level (also used as level for monochrome white)
        }
        """
        info("PETE#################### onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        device = Devices[Unit]
        channel_id = device.DeviceID
        if Command == "On":
            self.api_client.update_channel(channel_id, {"action": "TURN_ON"})
            channel_after_update = self.api_client.find_channel(channel_id)
            info("Channel After Update: " + str(channel_after_update))
            #update_device(channel_after_update, Unit)
            UpdateDevice(Unit, 1, 'On', Devices[Unit].TimedOut)
        elif Command == "Off":
            self.api_client.update_channel(channel_id, {"action": "TURN_OFF"})
            channel_after_update = self.api_client.find_channel(channel_id)
            info("Channel After Update: " + str(channel_after_update))
            #update_device(channel_after_update, Unit)
            UpdateDevice(Unit, 0, 'Off', Devices[Unit].TimedOut)
        elif Command == 'Set Level':
            # Set new level
            #dev.set_brightness(round(Level*2.55))
            info("Set Level: " + str(Level))
            self.api_client.update_channel(channel_id, {"action": "SET_RGBW_PARAMETERS", "brightness": Level })
            # Update status of Domoticz device
            UpdateDevice(Unit, 1 if Devices[Unit].Type == 241 else 2, str(Level), Devices[Unit].TimedOut)
        
        

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        """
        Called when any Domoticz device generates a notification. Name parameter is the device that generated the
        notification, the other parameters contain the notification details. Hardware that can handle notifications
        should be notified as required.
        """
        debug("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(
            Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        """
        Called after the remote device is disconnected, Connection is the Domoticz Connection object associated with
        the event

        This callback is not called for connectionless Transports such as UDP/IP.
        """
        debug("onDisconnect called")

    def onHeartbeat(self, force=False):
        """
        Called every 'heartbeat' seconds (default 10) regardless of connection status.

        Heartbeat interval can be modified by the Heartbeat command. Allows the Plugin to do periodic tasks including
        request reconnection if the connection has failed.

        Warning: Setting this interval to greater than 30 seconds will cause a 'thread seems to have ended unexpectedly'
        message to be written to the log file every 30 seconds. The plugin will function correctly but this message can
        not be suppressed because it is a standard warning from Domoticz that a piece of hardware may have stopped
        responding.

        If a plugin wants to heartbeat every 100 seconds it should be coded with the heartbeat interval set to 10, 20 or
        25 seconds and only take action every 6th, 5th or 4th time the callback is invoked.
        """
        debug("onHeartbeat called")
        now = datetime.datetime.now()
        #if force or (now - self.last_refresh).seconds > self.refresh_time:
        #    info("Updating devices...")
        #    self.last_refresh = now
        #    for unit in list(Devices.keys()):
        #        device = Devices[unit]
        #        channel_id = device.DeviceID
        #        channel = self.api_client.find_channel(channel_id)
        #        info("Channel Status: " + str(channel))
        #        update_device(channel, unit)
        #info("Devices: " + str(Devices))
        self.updateThread = threading.Thread(name="SUPLAUpdateThread", target=BasePlugin.handleThread, args=(self,))
        self.updateThread.start()

    # Separate thread looping every 10 seconds searching for new SUPLA on network and updating their status
    def handleThread(self):
        try:
            #info("Update")
            Domoticz.Debug("in handlethread")
            info("Updating devices...")
            #self.last_refresh = now
            #info("Call Create Devices")
            self.create_devices()
            #info("Call Update Devices")
            update_devices(self)

        except Exception as err:
            Domoticz.Error("handleThread: "+str(err)+' line '+format(sys.exc_info()[-1].tb_lineno))
            info("Error: " + str(err))


global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)


def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)


def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions


########################################################################################################################
#                                                    LOGGING                                                           #
########################################################################################################################

def info(msg):
    Domoticz.Log(msg)


def debug(msg):
    Domoticz.Debug(msg)
    #info(msg)


def status(msg):
    Domoticz.Status(msg)


def error(msg):
    Domoticz.Error(msg)


def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            info("'" + x + "':'" + str(Parameters[x]) + "'")
    info("Device count: " + str(len(Devices)))
    for x in Devices:
        info("Device:           " + str(x) + " - " + str(Devices[x]))
        info("Device ID:       '" + str(Devices[x].ID) + "'")
        info("Device Name:     '" + Devices[x].Name + "'")
        info("Device nValue:    " + str(Devices[x].nValue))
        info("Device sValue:   '" + Devices[x].sValue + "'")
        info("Device LastLevel: " + str(Devices[x].LastLevel))
    return

########################################################################################################################
#                                                    DEVICES                                                           #
########################################################################################################################
# Loop thru domoticz devices and see if there's a device with matching DeviceID, if so, return unit number, otherwise return zero
def getUnit(devid):
    unit = 0
    for x in Devices:
        if Devices[x].DeviceID == devid:
            unit = x
            break
    return unit

# Find the smallest unit number available to add a device in domoticz
def nextUnit():
    unit = 1
    while unit in Devices and unit < 255:
        unit = unit + 1
    return unit
