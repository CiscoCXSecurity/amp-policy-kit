#####################################################################################
# IMPORTS
#####################################################################################

import sys
import requests
import configparser
import time
import datetime
import dateutil
import gc
import json
from urllib.parse import urlparse, unquote
import argparse
import os
from xml.etree.ElementTree import fromstring, ElementTree,tostring

try:
    import xmltodict
    from bs4 import BeautifulSoup                  
except ImportError:
	print("[!] You do not appear to have either 'xmltodict' or 'BeautifulSoup' installed" )
	print("[!] Please execute 'pip3 install xmltodict beautifulsoup4' command. Exiting")
	sys.exit(0)

#####################################################################################
# HELPERS
#####################################################################################

# Ensure that file path is actually valid, to be used by ArgumentParser 'type' option
def validate_file(f):
    if not os.path.exists(f):
    	# Raise exception if specified path does not exist
        raise argparse.ArgumentTypeError("Path {0} does not exist".format(f))
    return f

# Quick validation of key elements before they are parsed
def validate_json_element(file_json, fields):
	try:
		x = file_json[fields]
		return True
	except KeyError:
		return False


#####################################################################################
# PARSERS
#####################################################################################


def parse_agentsettings(json_agent,json_object,product_type):
	# Check various scanning engines and their options for Windows
	if (product_type == 'windows'):
		print("[+] Specific Policy Misconfiguration:")

		if not validate_json_element(json_agent['ns0:control'],'ns0:passwordex'):
			print("\t[!]WARNING, AMP installation is not protected by password. Change this in 'Administrative Features > Enable Connector Protection'")

		# Check TTL on cloud lookups
		if validate_json_element(json_agent,'ns0:cloud'):
			cloud_settings = json_agent['ns0:cloud'] if "ns0:cloud" in str(json_agent) else None
			cloud_ttl = cloud_settings['ns0:cache']['ns0:ttl']
			if ( cloud_ttl != None):
				if (int(cloud_ttl['ns0:unknown']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on unknown hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:unknown'])))
				if (int(cloud_ttl['ns0:clean']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on clean hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:clean'])))
				if (int(cloud_ttl['ns0:malicious']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on malicious hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:malicious'])))
				if (int(cloud_ttl['ns0:unseen']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on unseen hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:unseen'])))
				if (int(cloud_ttl['ns0:block']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on block hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:block'])))

		# APDE = behavioral analytics
		if validate_json_element(json_agent,'ns0:apde'):
			apde_settings = json_agent['ns0:apde'] if "ns0:apde" in str(json_agent) else None
			if ( apde_settings != None):
				if (str(apde_settings['ns0:enable']) == '0'):
					print("\t[!]WARNING, Behavioral Protection is disabled. Change this in 'Modes and Engines > Behavioral Protection'")
				if (str(apde_settings['ns0:enable']) == '1' and str(apde_settings['ns0:mode']) == '0'):
					print("\t[!]WARNING, Behavioral Protection is set to AUDIT. Change this in 'Modes and Engines > Behavioral Protection'")

		# Check driver settings
		if validate_json_element(json_agent,'ns0:driver'):
			driver_settings = json_agent['ns0:driver'] if "ns0:driver" in str(json_agent) else None
			if ( driver_settings != None):
				if (str(driver_settings['ns0:blockexecqaction']) == '0' and str(driver_settings['ns0:protmode']['ns0:qaction']) == '0'):
					print("\t[!]WARNING, FILE protection is set to AUDIT. Change this in 'Modes and Engines > File'")

				if (str(driver_settings['ns0:protmode']['ns0:file']) == '0'):
					print("\t[!]WARNING, Monitor File Copies and Moves Execution is DISABLED. Change this in 'Advance Settings > File and Process Scan'")

				if (str(driver_settings['ns0:protmode']['ns0:process']) == '0'):
					print("\t[!]WARNING, Monitor Process Execution is DISABLED. Change this in 'Advance Settings > File and Process Scan'")

				if (str(driver_settings['ns0:selfprotect']['ns0:spp_qaction']) == '0'):
					print("\t[!]WARNING, System Process Protection is set to AUDIT. Change this in 'Modes and Engines > Malicious Activity Protection > System Process Protection'")

				if (str(driver_settings['ns0:selfprotect']['ns0:spp']) == '0' and str(driver_settings['ns0:selfprotect']['ns0:mkp']) == '0' and str(driver_settings['ns0:selfprotect']['ns0:sde']) == '0' and str(driver_settings['ns0:selfprotect']['ns0:spp_qaction']) == '1'):
					print("\t[!]WARNING, System Process Protection is set to DISABLED. Change this in 'Modes and Engines > Malicious Activity Protection > System Process Protection'")

				if (str(driver_settings['ns0:protmode']['ns0:activeexec']) == '0'):
					print("\t[!]WARNING, On Execute Mode is set to PASSIVE. Change this in 'Advance Settings > File and Process Scan'")

		# Check agent isolation
		if validate_json_element(json_agent,'ns0:endpointisolation'):
			agent_isolation_settings = json_agent['ns0:endpointisolation'] if "ns0:endpointisolation" in json_agent else None
			if(agent_isolation_settings != None):
				if (str(agent_isolation_settings['ns0:enable']) == '0'):
					print("\t[!]WARNING, Endpoint Isolation feature is disabled. Change this in 'Advance Settings > Endpoint Isolation'")
				if (str(agent_isolation_settings['ns0:enable']) == '1' and str(agent_isolation_settings['ns0:allowproxy']) == '1'):
					print("\t[!]WARNING, Endpoint Isolation feature is ENABLED and access to proxy is enabled. Change this in 'Advance Settings > Endpoint Isolation'")
				if (str(agent_isolation_settings['ns0:enable']) == '1' and str(agent_isolation_settings['ns0:allowproxy']) == '0'):
					print("\t[!]WARNING, Endpoint Isolation feature is ENABLED and access to proxy is disabled. Change this in 'Advance Settings > Endpoint Isolation'")

		# Check Orbital settings
		if validate_json_element(json_object['ns0:Signature']['ns0:Object']['ns0:config'],'ns0:orbital'):
			orbital_settings = json_object['ns0:Signature']['ns0:Object']['ns0:config']['ns0:orbital'] if "ns0:enablemsi" in json_object['ns0:Signature']['ns0:Object']['ns0:config']['ns0:orbital'] else None
			if(orbital_settings != None):
				if(str(orbital_settings['ns0:enablemsi']) == '0'):
					print("\t[!]WARNING, ORBITAL is disabled. Change this in 'Advance Settings > Orbital'")
	
		# Check scanner settings
		if validate_json_element(json_agent,'ns0:scansettings'):
			scanner_settings = json_agent['ns0:scansettings'] if "ns0:scansettings" in json_agent else None
			if (scanner_settings != None):
				if (str(scanner_settings['ns0:ethos']['ns0:enable']) == '0'):
					print("\t[!]WARNING, ETHOS engine is disabled. Change this in 'Advance Settings > Engines'")
				if (str(scanner_settings['ns0:ethos']['ns0:enable']) == '1' and str(scanner_settings['ns0:ethos']['ns0:file']) == '0'):
					print("\t[!]WARNING, ETHOS engine is ENABLED but ON COPY/MOVE scanning is disabled. Change this in 'Advance Settings > Engines'")
				if (str(scanner_settings['ns0:ssd']) == '0'):
					print("\t[!]WARNING, Monitoring of Network Drives is diabled. Change this in 'Advance Settings > Engines'")
				if (str(scanner_settings['ns0:spero']['ns0:enable']) == '0'):
					print("\t[!]WARNING, SPERO engine is disabled. Change this in 'Advance Settings > Engines'")
				if (str(scanner_settings['ns0:tetra']['ns0:enable']) == '0'):
					print("\t[!]WARNING, TETRA engine is disabled. Change this in 'Advance Settings > TETRA'")

			# Parse Tetra options
			tetra_options = scanner_settings['ns0:tetra']['ns0:options']['ns0:ondemand']
			if (tetra_options != None):
				if (str(tetra_options['ns0:scanarchives']) == '0' and str(scanner_settings['ns0:tetra']['ns0:enable']) == '1'):
					print("\t[!]WARNING, TETRA engine is ENABLED but ARCHIVE scan is disabled. Change this in 'Advance Settings > TETRA'")
				if (str(tetra_options['ns0:scanpacked']) == '0' and str(scanner_settings['ns0:tetra']['ns0:enable']) == '1'):
					print("\t[!]WARNING, TETRA engine is ENABLED but PACKED FILE scan is disabled. Change this in 'Advance Settings > TETRA'")
				if (str(tetra_options['ns0:deepscan']) == '0' and str(scanner_settings['ns0:tetra']['ns0:enable']) == '1'):
					print("\t[!]WARNING, TETRA engine is ENABLED but DEEP scan is disabled. Change this in 'Advance Settings > TETRA'")

			# Parse Malicious Activity Protection settings
			heuristic = json_agent['ns0:heuristic'] if "ns0:heuristic" in str(json_agent) else None
			if (heuristic != None):
				# Values - enabled & qaction 1 = 0 audit, enabled & qaction 1 = Quarantine, enabled & qaction = 2 block
				if (str(heuristic['ns0:enable']) == '0'):
					print("\t[!]WARNING, Malicious Activity Protection is DISABLED. Change this in 'Modes and Engines > Malicious Activity Protection'")
				if (str(heuristic['ns0:enable']) == '1' and str(heuristic['ns0:qaction']) == '0'):
					print("\t[!]WARNING, Malicious Activity Protection is ENABLED but set to AUDIT mode. Change this in 'Modes and Engines > Malicious Activity Protection'")
				if (str(heuristic['ns0:enable']) == '1' and str(heuristic['ns0:qaction']) == '1'):
					print("\t[!]WARNING, Malicious Activity Protection is ENABLED but set to QUARANTINE mode. Change this in 'Modes and Engines > Malicious Activity Protection'")

			# Parse exploit prevention settings
			exploit_prevention = json_agent['ns0:exprev']['ns0:enable'] if "ns0:exprev" in str(json_agent) else None
			if (exploit_prevention != None):
				if (str(exploit_prevention) == '0'):
					print("\t[!]WARNING, Exploit Prevention is disabled. Change this in 'Modes and Engines > Exploit Protection'")
				if (str(exploit_prevention) == '1' and str(json_agent['ns0:exprev']['ns0:v4']['ns0:options'] == '0x0000033B')):
					print("\t[!]WARNING, Exploit Prevention is set to AUDIT. Change this in 'Modes and Engines > Exploit Protection'")

			# Parse AMSI engine settings
			amsi_settings = json_agent['ns0:amsi'] if "ns0:amsi" in str(json_agent) else None
			if (amsi_settings != None):
				if (str(amsi_settings['ns0:enable']) == '0'):
					print("\t[!]WARNING, Script Protection engine is disabled. Change this in 'Modes and Engines > Script Protection'")
				if (str(amsi_settings['ns0:enable']) == '1' and str(amsi_settings['ns0:mode']) == '0'):
					print("\t[!]WARNING, Script Protection is ENABLED and engine is set to AUDIT. Change this in 'Modes and Engines > Script Protection'")

	# Check various scanning engines and their options for Mac or Linux
	if (product_type == 'mac' or product_type == 'linux'):
		print("[+] Specific Policy Misconfiguration:")
		# Check TTL on cloud lookups
		if validate_json_element(json_agent,'ns0:cloud'):
			cloud_settings = json_agent['ns0:cloud'] if "ns0:cloud" in str(json_agent) else None
			cloud_ttl = cloud_settings['ns0:cache']['ns0:ttl']
			if ( cloud_ttl != None):
				if (int(cloud_ttl['ns0:unknown']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on unknown hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:unknown'])))
				if (int(cloud_ttl['ns0:clean']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on clean hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:clean'])))
				if (int(cloud_ttl['ns0:malicious']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on malicious hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:malicious'])))
				if (int(cloud_ttl['ns0:unseen']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on unseen hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:unseen'])))
				if (int(cloud_ttl['ns0:block']) > 3600):
					print("\t[!]WARNING, Potentially long TTL on block hash lookup : {}. Change this in 'Advance Settings > Cache'".format(int(cloud_ttl['ns0:block'])))
		
		# Check DRIVER settings
		if validate_json_element(json_agent,'ns0:driver'):
			driver_settings = json_agent['ns0:driver'] if "ns0:driver" in str(json_agent) else None
			if (driver_settings != None):
				if (str(driver_settings['ns0:protmode']['ns0:qaction']) == '0'):
					print("\t[!]WARNING, FILE blocking is set to AUDIT mode. Change this in 'Modes and Engines > Conviction Modes > Files'")
				if (str(driver_settings['ns0:protmode']['ns0:process']) == '0'):
					print("\t[!]WARNING, Monitor Process Execution is DISABLED. Change this in 'Advance Settings > File and Process Scan'")
				if (str(driver_settings['ns0:protmode']['ns0:file']) == '0'):
					print("\t[!]WARNING, Monitor File Copies and Moves Execution is DISABLED. Change this in 'Advance Settings > File and Process Scan'")
				if (str(driver_settings['ns0:protmode']['ns0:activeexec']) == '0'):
					print("\t[!]WARNING, On Execute Mode is set to PASSIVE. Change this in 'Advance Settings > File and Process Scan'")


		if validate_json_element(json_agent,'ns0:scansettings'):
			scanner_settings = json_agent['ns0:scansettings'] if "ns0:scansettings" in json_agent else None
			# Clam AV engine checks
			clam_av = scanner_settings['ns0:clamav']
			if (clam_av != None):
				if (str(clam_av['ns0:enable']) == '0'): 
					print("\t[!]WARNING, CLAMAV engine is disabled. Change this in 'Advance Settings > ClamAV'")

	################# OTHER PARSERS - MAC + WINDOWS + LINUX

	# Parse NFM settings
	if validate_json_element(json_agent,'ns0:nfm'):
		nfm_settings = json_agent['ns0:nfm'] if "ns0:nfm" in str(json_agent) else None
		if ( nfm_settings != None):
			if (str(nfm_settings['ns0:enable']) == '0'):
				print("\t[!]WARNING, Network/Device Flow Monitoring is disabled. Change this in 'Advance Settings > Network'")
			if (str(nfm_settings['ns0:enable']) == '1' and str(nfm_settings['ns0:settings']['ns0:qaction']) == '0'):
				print("\t[!]WARNING, Network/Device Flow Monitoring is ENABLED but set AUDIT. Change this in 'Advance Settings > Network'")


	# Parse CMD settings
	if validate_json_element(json_agent,'ns0:cmdlinecapture'):
		cmd_settings = json_agent['ns0:cmdlinecapture'] if "ns0:cmdlinecapture" in str(json_agent) else None
		if (cmd_settings != None):
			if (str(cmd_settings['ns0:enable']) == '0'):
				print("\t[!]WARNING, Command line capture is disabled. Change this in 'Advance Settings > Administrative Feature > Command Line Capture'")

	# UI settings
	if validate_json_element(json_object['ns0:Signature']['ns0:Object']['ns0:config'],'ns0:ui'):
		UI_settings = json_object['ns0:Signature']['ns0:Object']['ns0:config']['ns0:ui']
		# Different UI settings depending on product version
		if (product_type == 'mac'):
			if(UI_settings != None):
				if(UI_settings['ns0:exclusions']['ns0:display'] == "1"):
					print("\t[!]WARNING, EXCLUSIONS are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:cloud'] == "1"):
					print("\t[!]WARNING, CLOUD notification are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:hide_file_toast'] == "0"):
					print("\t[!]WARNING, FILE notification are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:hide_nfm_toast'] == "0"):
					print("\t[!]WARNING, NETWORK FLOW notification are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:verbose'] == "1"):
					print("\t[!]WARNING, VERBOSE logs are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")

		elif (product_type == 'windows'):
			if(UI_settings != None):
				if(UI_settings['ns0:exclusions']['ns0:display'] == "1"):
					print("\t[!]WARNING, EXCLUSIONS are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:cloud'] == "1"):
					print("\t[!]WARNING, CLOUD notification are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:hide_file_toast'] == "0"):
					print("\t[!]WARNING, FILE notification are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:hide_nfm_toast'] == "0"):
					print("\t[!]WARNING, NETWORK FLOW notification are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:verbose'] == "1"):
					print("\t[!]WARNING, VERBOSE logs are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:hide_ioc_toast'] == "0"):
					print("\t[!]WARNING, IOC logs are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:hide_detection_toast'] == "0"):
					print("\t[!]WARNING, DETECTION logs are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:hide_heuristic_toast'] == "0"):
					print("\t[!]WARNING, HEURISTIC logs are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")
				if(UI_settings['ns0:notification']['ns0:hide_exprev_toast'] == "0"):
					print("\t[!]WARNING, EXPLOIT PREVENTION logs are shown to users via GUI. Change this in 'Advance Settings > Client User Interface'")


# Define parser for basic policy metadata stored in header
def parse_header(json_header, product):
	if(len(json_header) != 0 ):
		if validate_json_element(json_header,'ns0:policy'):
			if(len(json_header['ns0:policy']) > 1 ):
				print("[+] Policy Name: {}".format(json_header['ns0:policy']['ns0:name']))
				print("[+] Policy Product: {}".format(product))
				print("[+] Policy GUID: {}".format(json_header['ns0:policy']['ns0:uuid']))
				print("[+] Policy Version: {}".format(json_header['ns0:policy']['ns0:serial_number']))
				print("[+] Business GUID: {}".format(json_header['ns0:business']['ns0:uuid']))
				timestamp = json_header['ns0:policy']['ns0:updated']
				current_time_utc = datetime.datetime.utcnow()
				converted_d1 = datetime.datetime.fromtimestamp(round(int(timestamp) / 1000))
				print("[!] WARNING, Last policy change: {} ago".format((current_time_utc - converted_d1)))
		
# Define parser for policy exclusions
def parse_exclusions(json_exclusion):
	if(len(json_exclusion) != 0 ):
		if validate_json_element(json_exclusion['ns0:info'],'ns0:item'):
			if(len(json_exclusion['ns0:info']['ns0:item']) > 1 and json_exclusion['ns0:info'] != None):
				print("[+] File Exclusions in policy: ")
				if(len(json_exclusion['ns0:info']['ns0:item']) > 1 ):
					for e in json_exclusion['ns0:info']['ns0:item']:
						if ("*" in e.split("|")[4]):
							print("\tWARNING, wildecard : {} ".format(unquote(e.split("|")[4])))
						else:
							print("\t", unquote(e.split("|")[4]))
				else:
					print("\t", str(unquote(json_exclusion['ns0:info']['ns0:item']).split("|")[4]))
		else:
			print("[+] No path exclusions are defined")
		if validate_json_element(json_exclusion,'ns0:certissuer'):
			if("certissuer" in str(json_exclusion)):
				print("[+] Certificate Exclusions in policy: ")
				if(len(json_exclusion['ns0:certissuer']['ns0:name']) > 1 and json_exclusion['ns0:certissuer'] != None):
					for e in json_exclusion['ns0:certissuer']['ns0:name']:
						if ("*" in e):
							print("\tWARNING, wildecard : {} ".format(unquote(e)))
						else:
							print("\t", unquote(e))
				else:
					print("\t",unquote(json_exclusion['ns0:certissuer']['ns0:name']))
		else:
			print("[+] No certificate issuer exclusions are defined")

		if validate_json_element(json_exclusion,'ns0:process'):
			if ("process" in str(json_exclusion) and json_exclusion['ns0:process'] != None):
				print("[+] Process Exclusions in policy: ")
				# A bit hacky way of working out if there is more than 1 element in list
				if ("', '" in str(json_exclusion['ns0:process']['ns0:item'])):
					for e in json_exclusion['ns0:process']['ns0:item']:
						if ("*" in e):
							print("\tWARNING, wildecard : {} ".format(unquote(e)))
						else:
							print("\t", unquote(e))
				else:
					single_exclusion = json_exclusion['ns0:process']['ns0:item']
					if ("*" in single_exclusion):
						print("\tWARNING, wildecard : {} ".format(unquote(single_exclusion)))
					else:
						print("\t", unquote(single_exclusion))
		else:
			print("[+] No process exclusions are defined")

#####################################################################################
# MAIN
#####################################################################################

def main():
	# Parse arguments
	ap = argparse.ArgumentParser()
	ap.add_argument("-i", "--input", dest="config_path", required=True, help="path to AMP XML config file", type=validate_file, metavar="FILE")
	args = ap.parse_args()

	f = open(args.config_path,"r")
	# Build tree
	tree = ElementTree(fromstring(f.read()))
	# Get root element of the policy
	root = tree.getroot()
	# Parse element to into json structure so we can extract specific elements. There is easier way of doing this but it will need to do for now.
	b4_xml_obj = BeautifulSoup(tostring(root), "xml")
	pdic = xmltodict.parse(b4_xml_obj.prettify(),dict_constructor=dict)
	pdic_json = json.dumps(pdic)
	json_object = json.loads(pdic_json)

	# define certain key headers
	try:
		
		# Policy header is in every policy
		policy_header = json_object['ns0:Signature']['ns0:Object']['ns0:config']['ns0:janus']
		
		# Ensure exclusions are present
		if validate_json_element(json_object['ns0:Signature']['ns0:Object']['ns0:config'],'ns0:exclusions'):
			exclusions = json_object['ns0:Signature']['ns0:Object']['ns0:config']['ns0:exclusions']
		else:
			exclusions = None
		# Ensure agent settings are present
		if validate_json_element(json_object['ns0:Signature']['ns0:Object']['ns0:config'],'ns0:agent'):
			agentconfig = json_object['ns0:Signature']['ns0:Object']['ns0:config']['ns0:agent']
		else:
			agentconfig = None

		policy_type = ""

		# A 'simple' way of finding product type. Policy file does not contain that information so we are improvising here
		# Before we invoke any parser, lets make sure that there are some policies present 
		if (exclusions != None):
			if("Spotlight" in str(exclusions) or "Library" in str(exclusions)):
				policy_type = "mac"
				parse_header(policy_header,policy_type)
				parse_exclusions(exclusions)
				if (agentconfig != None):
					parse_agentsettings(agentconfig,json_object,policy_type)
			elif ("CSIDL_WINDOWS" in str(exclusions)):
				policy_type = "windows"
				parse_header(policy_header,policy_type)
				parse_exclusions(exclusions)
				if (agentconfig != None):
					parse_agentsettings(agentconfig,json_object,policy_type)
			else: # it can be either network policy or linux
				policy_type = "linux"
				parse_header(policy_header,policy_type)
				parse_exclusions(exclusions)
				if (agentconfig != None):
					parse_agentsettings(agentconfig,json_object,policy_type)
		# Attempt to parse settings event if exclusion list is not present
		elif (agentconfig != None):
			if("Spotlight" in str(exclusions) or "Library" in str(exclusions)):
				policy_type = "mac"
				parse_header(policy_header,policy_type)
				parse_agentsettings(agentconfig,json_object,policy_type)
			elif ("CSIDL_WINDOWS" in str(exclusions)):
				policy_type = "windows"
				parse_header(policy_header,policy_type)
				parse_agentsettings(agentconfig,json_object,policy_type)
			else:
				policy_type = "linux"
				parse_header(policy_header,policy_type)
				parse_agentsettings(agentconfig,json_object,policy_type)

	except KeyError as e:
		print(repr(e))
		print("\t[!] No security settings present (could be Network-only) policy")
		sys.exit(1)

if __name__ == "__main__":
    main()