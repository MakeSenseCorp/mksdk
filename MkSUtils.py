import socket
import os
import sys
import subprocess
import re
from array import array
import struct
import netifaces

class IPNetwork():
	def __init__(self):
		self.Interfaces = []
		self.IPs 		= []
		self.Gateway 	= []

		self.Interfaces = netifaces.interfaces()
		for network in self.Interfaces:
			addrs = netifaces.ifaddresses(network)
			if netifaces.AF_INET in addrs:
				if len(addrs[netifaces.AF_INET]) > 0:
					self.IPs.append({
						"ip": addrs[netifaces.AF_INET][0],
						"iface": network
					})

	def GetNetworkInterfaces(self):
		return self.Interfaces
	
	def GetIPAdresses(self):
		return self.IPs

class Utils():
	def __init__(self):
		pass

# LocalSocketMngr & AbstructNode
def GetIPList():
	ip_list = []

	net = IPNetwork()
	for ip in net.GetIPAdresses():
		ip_list.append({
			'iface':ip["iface"],
			'ip': ip["ip"]["addr"],
			'mask': ip["ip"]["netmask"],
			'mac': "00-00-00-00-00-00"
		})
	return ip_list

def GetLocalIP():
	ip = socket.gethostbyname(socket.gethostname())
	print(ip)
	if ip.startswith("127.") and os.name != "nt":
		interfaces = [
			"eth0",
			"eth1",
			"eth2",
			"wlan0",
			"wlan1",
			"wifi0",
			"ath0",
			"ath1",
			"ppp0",
			"enp0s3",
			"wlp2s0"
			]
		for ifname in interfaces:
			try:
				ip = get_interface_ip(ifname)
				break
			except IOError:
				pass
	return ip

def Ping(address):
	response = 1
	if os.name != "nt":
		response = subprocess.call("ping -c 1 %s" % address, shell=True, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)
	else:
		#response = subprocess.call("ping %s -n 1" % address, shell=True, stdout=subprocess.PIPE,stdin=subprocess.PIPE, stderr=subprocess.PIPE)
		#response = os.system('ping %s -n 1 > NUL' % (address,))
		ps  = subprocess.Popen('ping %s -n 1' % (address,),shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
		out = ps.communicate()
		if len(out) > 0:
			cmd_out = out[0].decode("utf-8") 
			if "Request timed out." in cmd_out or "Destination host unreachable." in cmd_out:
				response = 1
			else:
				response = 0
	# Check response
	if response == 0:
		return True
	else:
		return False

def ScanLocalNetwork(network_ip):
	machines = []
	for i in range(1, 32):
		IPAddress = network_ip + str(i)
		res = Ping(IPAddress)
		if True == res:
			machines.append(IPAddress)
	return machines

def ScanLocalNetworkForMasterPort(network_ip):
	machines = []
	for i in range(1, 16):
		IPAddress = network_ip + str(i)

		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		serverAddr = (IPAddress, 16999)
		sock.settimeout(1)
		try:
			sock.connect(serverAddr)
			machines.append(IPAddress)
			sock.close()
		except:
			pass
	return machines

# Locking for Server Nodes and getting list of Nodes 
# attached to each machine.
def FindLocalMasterNodes():
	localIP = GetLocalIP()
	networkIP = '.'.join((localIP.split('.'))[:-1]) + '.'
	machines = ScanLocalNetworkForMasterPort(networkIP)
	return machines

def ReadFromSocket(ip, port, data, size=1024):
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	serverAddr = (ip, port)
	sock.settimeout(1)
	try:
		sock.connect(serverAddr)
		sock.sendall(data)
		response = sock.recv(size)
		sock.close()
		return response
	except:
		print ("ERROR")
		sock.close()
		return ""