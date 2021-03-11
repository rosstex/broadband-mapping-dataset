'''
This file contains an API for checking whether various ISPs cover a given address.
PARAMETERS: 
	isp: the name of an internet service provider
	address: a U.S. address (as an Address object - see Address.py)
	debug: a boolean whether the tool should print the full response to stdout (usually for debugging)
RETURNS:
	an int reprenting a response from the ISP (see below for full list)
	*** In some cases, there are just integers to indicate responses in the code (without a corresponding string in RESPONSES)
		below. Usually, this is just a placeholder in case the case ever actually came up when running on our dataset (which it didn't).

'''
from street_prefixes import STREET_PREFIXES
import re
import time
import requests
import pprint
import random
import copy
from bs4 import BeautifulSoup
import json
from CoverageResult import CoverageResult
from UserAgents import user_agents, user_agents_ipad, user_agents_charter_browser, user_agents_charter_old
from luminati_proxies import luminati_proxies
from Address import Address
import traceback

pp = pprint.PrettyPrinter(indent=4)
EXCEPTION_MESSAGE = 'Not fully implemented! I.e., we never tested for this ISP\'s coverage at scale...'

# All response "buckets"
NOT_COVERED = 0
COVERED_GENERAL = 1
COVERED_EXISTS = 2
COVERED_NOT_EXISTS = 3
NOT_RECOGNIZED = 4
BUSINESS = 5
COVERED_BUILDING = 6
BUILDING_UNKNOWN = 7
UNKNOWN = 30


RESPONSES = {
	'altice': {
		'NO_SPEED': 20,
		'NO_INTERNET': 21,
		'UNSUPPORTED_BROWSER': 22,
		'COVERED_NO_MATCH': 23,
	},
	'att' : {
		'BOTH' : 20,
		'LIGHT_GIG': 21,
		'LIGHT_SPEED': 22,
		'ADDRESSES_DO_NOT_MATCH' : 23,
		'PROCESS_ERROR' : 24,
		'CLOSEMATCH' : 25,
		'NOT_DONE': 26,
		'RED_ISSUE': 27,
	},
	'centurylink' : {
		'NOT_COVERED_CALL' : 20,
		'NOT_COVERED_KBPS' : 21,
		'ADDRESS_MISMATCH' : 22,
		'SYSTEM_ISSUES' : 23,
		'CONTACT_US': 24,
	},
	'charter': {
		'NOT_COVERED_SERVICEABLE': 20,
		'NOT_COVERED_ZIP': 21,
		'NO_MATCHING_ADDRESS': 22,
		'NOT_COVERED_ZIP4': 23,
		'CALL_TO_VERIFY': 24,
		'NO_SERVICE_STATUS_VERIFY': 25,
		'CALL_TO_VERIFY_NO_COVERAGE_ACTUAL': 26,
		'COVERED_FORMER': 27,
		'COVERED_ACTIVE': 28,
		'NOT_COVERED_HSD_FALSE':29, # 0
		'NEVER_SERVICE_STATUS':60,
		'NO_MATCHING_ADDRESS_SMARTY':61,
		'HSD_TRUE_SERVICESTAT_NEVER': 62
	},
	'consolidated': {
		'NOT_COVERED_ZIP': 20,
		'ADDRESS_NOT_FOUND': 21,
		'NO_MATCHING_ADDRESS': 22,
		'NO_CONTROL_NUM':23,
	},
	'frontier' : {
		'NOT_COVERED_UNDER': 21,
		'HAVING_TROUBLE': 22,
		'HAVING_TROUBLE_PRODUCTS': 23,
	},
	'verizon' : {
		'NOT_COVERED_ZIP': 21,
		'GET_SPEED_ERROR': 22,
		'ADDRESS_DOES_NOT_MATCH':23,
		'NO_ADDRESS_MATCH':24, # Verizon offers some addresses as a possible match, but they do not match. 
		'FIOS_EARLY_COVERED': 25,
	},
	'windstream' : {
		'WE_CANT_FIND_ZIP': 20,
		'ZIP_CODE_NOT_FOUND_CALL': 21,
		'NO_INTERNET': 22,
		'WE_CANT_FIND_ADDRESS': 23,
		'UQAL_NOT_REACHABLE': 24,
	},
	'xfinity' : {
		'SORRY': 20,
		'EXTRAATTENTION': 29,
		'BULKTENANT': 28,
		'COMMUNITY': 21,

	}
}

class IspApiTool:
	def __init__(self):
		# List of all the ISP APIs we currently cover in the tool
		self.apis = [
			'att',
			'cable_one',
			'centurylink',
			'charter',
			'cincinnati',
			'consolidated',
			'cox',
			'earthlink'
			'frontier',
			'hawaii',
			'mediacom',
			'optimum',
			'sonic',
			'suddenlink',
			'tds_telecom',
			'verizon',
			'windstream',
			'xfinity',
		]

	''' 
	RETURNS: list of all covered APIs
	'''
	def list_covered_apis(self):
		return self.apis

	''' 
	Make a request to a given ISP API:
	ARGS:
	ISP (type string): whichever ISP (from the list), you are sending the request to
	Address (type Address): address of the household you are checking
	RETURNS: integer representing a response from the ISP
	'''
	def make_request(self, isp, address, debug, proxy=None, retries = 0, data=None):

		# Copy address and remove apartments that are just blank spaces - DEPRECATED
		'''
		address = copy.copy(address)
		if address.apt_type == ' ':
			address.apt_type = ''
		if address.apt_number == ' ':
			address.apt_number = ''
		'''

		# If there is an apartment type, but not number, let's move it to number - DEPRECATED
		'''
		if address.apt_type != '' and address.apt_number == '':
			address.apt_number = address.apt_type 
			address.apt_type = ''
		'''

		# Replace * in address (weird formatting thing for some addresses)
		if '*' in address.line1:
			address.line1 = address.line1.replace('*','')

		# Set up proxy
		if proxy == None:
			proxies = None
		elif proxy == 'luminati':
			luminati_ip = random.choice(luminati_proxies)
			proxies = {
				'http': 'http://lum-customer-princeton_uni-zone-static:shpwxvkqxfai@zproxy.lum-superproxy.io:22225', 
				'https': 'http://lum-customer-princeton_uni-zone-static:shpwxvkqxfai@zproxy.lum-superproxy.io:22225'
			}
		elif proxy == 'luminati-us':
			luminati_ip = random.choice(luminati_proxies)
			proxies = {
				'http': 'http://lum-customer-princeton_uni-zone-static-country-us:shpwxvkqxfai@zproxy.lum-superproxy.io:22225', 
				'https': 'http://lum-customer-princeton_uni-zone-static-country-us:shpwxvkqxfai@zproxy.lum-superproxy.io:22225'
			}
		elif proxy == 'luminati-r':
			proxies = {
				'http': 'http://lum-customer-princeton_uni-zone-residential-country-us:u309oeza1seq@zproxy.lum-superproxy.io:22225',
		    	'https': 'http://lum-customer-princeton_uni-zone-residential-country-us:u309oeza1seq@zproxy.lum-superproxy.io:22225'
			}
		else:
			proxies = {'http': 'http://djmajor97:ededed111@{}'.format(proxy), 'https': 'http://djmajor97:ededed111@{}'.format(proxy)}

		proxies_us = {
			'http': 'http://lum-customer-princeton_uni-zone-static-country-us:shpwxvkqxfai@zproxy.lum-superproxy.io:22225', 
			'https': 'http://lum-customer-princeton_uni-zone-static-country-us:shpwxvkqxfai@zproxy.lum-superproxy.io:22225'
		}
		proxies_r = {
			'http': 'http://lum-customer-princeton_uni-zone-residential-country-us:u309oeza1seq@zproxy.lum-superproxy.io:22225',
	    	'https': 'http://lum-customer-princeton_uni-zone-residential-country-us:u309oeza1seq@zproxy.lum-superproxy.io:22225'
		}

		# Just for formatting for some ISPs
		if address.apt_type == None:
			address.apt_type = ''
		if address.apt_number == None:
			address.apt_number = ''
		apt = ''
		if address.apt_number != '':
			if address.apt_type == '':
				apt = address.apt_number
			else:
				apt = address.apt_type + ' ' + address.apt_number

		# Randomely select a user agent
		user_agent = random.choice(user_agents)

		# ISP: AT&T
		if isp == 'att':

			s = requests.session()

			url = 'https://www.att.com/msapi/serviceavailability/v1/address'

			headers = {
				'Sec-Fetch-Mode': 'cors',
				'Origin': 'https://www.att.com',
				'User-Agent':user_agent,
				'content-type':'application/json',
				'Accept':'*/*',
				'origin': 'https://www.att.com',
				'referer': 'https://www.att.com/buy/bundles?product_suite=NBB',
			}

			body = {
				"customerType":"consumer", # auto, unclear if business is different
				"mode":"fullAddress",
				"userInputAddressLine1":address.line1,
				"userInputZip":address.zipcode
			}

			# When AT&T doesn't recognize an address (they do it based on SmartyStreets), they submit the address to the API with the full address
			if data != None and data.get('previously_unrecognized') == True:
				body["userInputAddressLine1"] = address.fullAddress()

			r = s.post(url=url, json=body, headers=headers, proxies=proxies)
			response = r.json()

			if debug == True:
				pp.pprint(response)

			if 'error' in response:
				if 'Sorry we could not process your request at this time. Please try again later.' in response.get('error').get('message'):
					return {
						70 : CoverageResult(is_covered=RESPONSES['att']['PROCESS_ERROR']),
						10 : CoverageResult(is_covered=RESPONSES['att']['PROCESS_ERROR']),
						50 : CoverageResult(is_covered=RESPONSES['att']['PROCESS_ERROR']),
					}
				else:
					return {
						70 : CoverageResult(is_covered=104),
						10 : CoverageResult(is_covered=104),
						50 : CoverageResult(is_covered=104),
					} 

			response = response.get('content')

			# It's an apartment building and they suggest addresses
			if response.get('availabilityStatus') == 'MDU':

				unit_index = -1
				for i, apt_json in enumerate(response.get('mduAddress')):
					unit_index = i
					break
				if unit_index == -1:
					return {
						70 : CoverageResult(is_covered=30),
						10 : CoverageResult(is_covered=30),
						50 : CoverageResult(is_covered=30),
					} 
				body = {
					'customerType': "consumer",
					'index': str(unit_index),
					'mode': "MDU",
				}

				r = s.post(url=url, json=body, headers=headers, proxies=proxies)
				response = r.json()

				if debug == True:
					pp.pprint(response)

				if 'error' in response:
					if 'Sorry we could not process your request at this time. Please try again later.' in response.get('error').get('message'):
						return {
							70 : CoverageResult(is_covered=RESPONSES['att']['PROCESS_ERROR']),
							10 : CoverageResult(is_covered=RESPONSES['att']['PROCESS_ERROR']),
							50 : CoverageResult(is_covered=RESPONSES['att']['PROCESS_ERROR']),
						} 
					else:
						return {
							70 : CoverageResult(is_covered=104),
							10 : CoverageResult(is_covered=104),
							50 : CoverageResult(is_covered=104),
						} 
				response = response.get('content')
			elif response.get('availabilityStatus') == 'NOMATCH':
				if data == None:
					return self.make_request(isp=isp, address=address, debug=debug, proxy=proxy, retries = retries, data={'previously_unrecognized':True})
				elif data.get('previously_unrecognized') == True:
					return {
						70 : CoverageResult(is_covered=NOT_RECOGNIZED),
						10 : CoverageResult(is_covered=NOT_RECOGNIZED),
						50 : CoverageResult(is_covered=NOT_RECOGNIZED),
					} 
				else:
					return {
						70 : CoverageResult(is_covered=300),
						10 : CoverageResult(is_covered=300),
						50 : CoverageResult(is_covered=300),
					} 

			coverages = dict()
			if response.get('availabilityStatus') in ['GREEN', 'EXISTINGSERVICESFOUND', 'RED']:

				available_or_existing = None
				if response.get('availabilityStatus') == 'GREEN':
					available_or_existing = COVERED_NOT_EXISTS
				elif response.get('availabilityStatus') == 'EXISTINGSERVICESFOUND':
					available_or_existing = COVERED_EXISTS
				elif response.get('availabilityStatus') == 'RED':
					available_or_existing = COVERED_NOT_EXISTS
				else:
					return {
						70 : CoverageResult(is_covered=RESPONSES['att']['RED_ISSUE']),
						10 : CoverageResult(is_covered=RESPONSES['att']['RED_ISSUE']),
						50 : CoverageResult(is_covered=RESPONSES['att']['RED_ISSUE']),
					}  

				# Confirm address is the same
				if address.line1.replace(" ","") not in response.get('addressFeatures').get('addressLine1').replace(" ","") or address.zipcode != response.get('addressFeatures').get('zip'):
					
					return {
						70 : CoverageResult(is_covered=RESPONSES['att']['ADDRESSES_DO_NOT_MATCH']),
						10 : CoverageResult(is_covered=RESPONSES['att']['ADDRESSES_DO_NOT_MATCH']),
						50 : CoverageResult(is_covered=RESPONSES['att']['ADDRESSES_DO_NOT_MATCH']),
					} 

				address_id = response.get('addressFeatures').get('addressId')

				# Checking if these cases exists:
				if response.get('availableServices').get('lightGigAvailable') == True and response.get('availableServices').get('lightSpeedAvailable') == False:
					return {
						70 : CoverageResult(is_covered=100),
						10 : CoverageResult(is_covered=100),
						50 : CoverageResult(is_covered=100),
					} 
				# Rare case that I left in to check if it exists ever (which it does in rare cases). Manually tried out ~15 cases and they all returned as not covered 
				if (response.get('availableServices').get('hsiaAvailable') == True and (response.get('availableServices').get('lightGigAvailable') == False and response.get('availableServices').get('lightSpeedAvailable') == False)) or (response.get('availableServices').get('hsiaAvailable') == False and (response.get('availableServices').get('lightGigAvailable') == True or response.get('availableServices').get('lightSpeedAvailable') == True)):
					if response.get('availableServices').get('hsiaAvailable') == False and (response.get('availableServices').get('lightGigAvailable') == True or response.get('availableServices').get('lightSpeedAvailable') == True):
						coverages[50] = CoverageResult(is_covered=NOT_COVERED)
						coverages[10] = CoverageResult(is_covered=NOT_COVERED)
						if response.get('availableServices').get('fixedWirelessInternetAvailable') == True:
							coverages[70] = CoverageResult(is_covered=available_or_existing)
						else:
							coverages[70] = CoverageResult(is_covered=NOT_COVERED)
						return coverages
					else:
						return {
							70 : CoverageResult(is_covered=101),
							10 : CoverageResult(is_covered=101),
							50 : CoverageResult(is_covered=101),
						} 
				# -----

				if response.get('availableServices').get('connectedCommunity') == True:
					print("\n\nCONNECTED COMMUNITY!!" + address.fullAddress())
				# Skip dtvAvailable - irrelevant to internet
				
				if response.get('availableServices').get('fixedWirelessInternetAvailable') == True:
					coverages[70] = CoverageResult(is_covered=available_or_existing)
				else:
					coverages[70] = CoverageResult(is_covered=NOT_COVERED)
				
				'''
				# We tested this case to understand whether it corresponds with coverage (and differentiates from 'lightSpeedAvailable')
				if response.get('availableServices').get('hsiaAvailable') == True:
					coverages[10] = CoverageResult(is_covered=COVERED_GENERAL)
				else:
					coverages[10] = CoverageResult(is_covered=NOT_COVERED)
				'''

				# SKIP iptv - relevant to internet

				if response.get('availableServices').get('lightGigAvailable'):
					coverages[50] = CoverageResult(is_covered=available_or_existing)
				else:
					coverages[50] = CoverageResult(is_covered=NOT_COVERED)
				
				if response.get('availableServices').get('lightSpeedAvailable'):
					coverages[10] = CoverageResult(is_covered=available_or_existing)
				else:
					coverages[10] = CoverageResult(is_covered=NOT_COVERED)

				# Skip voip
			elif response.get('availabilityStatus') == 'NOMATCH':
				return {
					70 : CoverageResult(is_covered=NOT_RECOGNIZED),
					10 : CoverageResult(is_covered=NOT_RECOGNIZED),
					50 : CoverageResult(is_covered=NOT_RECOGNIZED),
				} 
			elif response.get('availabilityStatus') == 'CLOSEMATCH':
				return {
					70 : CoverageResult(is_covered=RESPONSES['att']['CLOSEMATCH']),
					10 : CoverageResult(is_covered=RESPONSES['att']['CLOSEMATCH']),
					50 : CoverageResult(is_covered=RESPONSES['att']['CLOSEMATCH']),
				} 
			elif response.get('availabilityStatus') == 'NOTDONE':
				return {
					70 : CoverageResult(is_covered=RESPONSES['att']['NOT_DONE']),
					10 : CoverageResult(is_covered=RESPONSES['att']['NOT_DONE']),
					50 : CoverageResult(is_covered=RESPONSES['att']['NOT_DONE']),
				} 
			else:
				return {
					70 : CoverageResult(is_covered=34),
					10 : CoverageResult(is_covered=34),
					50 : CoverageResult(is_covered=34),
				} 

			# Get speed for DSL/fiber if the address is covered.
			if coverages[10].is_covered in [COVERED_EXISTS, COVERED_NOT_EXISTS] or coverages[50].is_covered in [COVERED_EXISTS, COVERED_NOT_EXISTS]:
				url = 'https://www.att.com/msapi/salesproductorchestration/v1/baseOffers'
				headers = {
					'accept': '*/*',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					'content-length': '70',
					'content-type': 'application/json',
					'origin': 'https://www.att.com',
					'referer': 'https://www.att.com/buy/bundles?product_suite=NBB',
					'sec-fetch-dest': 'empty',
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					'user-agent': user_agent,
				}
				body = {
					"channel":"Online",
					"useCache":True,
					"broadband":{
						"offerType":"offer"
					}
				}
				r = s.post(url=url, json=body, headers=headers, proxies=proxies)

				response = r.json()

				if 'error' in response:
					return CoverageResult(is_covered=33)

				offers = response.get('content').get('broadband').get('baseOffers')
				max_downspeed = -1
				max_upspeed = -1
				for offer in offers:
					if debug == True:
						pp.pprint(offer)

					if offer.get('displayName') == 'Internet':
						product = offer.get('product')
						down_speed = product.get('downloadSpeed').get('speed')
						if product.get('downloadSpeed').get('uom') == 'Mbps':
							pass
						elif product.get('downloadSpeed').get('uom') == 'Kbps':
							down_speed = float(down_speed/1000)
						else:
							print('NON MBPS/KPBS HERE: ' + address.fullAddress())
							return {
								70 : CoverageResult(is_covered=32),
								10 : CoverageResult(is_covered=32),
								50 : CoverageResult(is_covered=32),
							} 
						if down_speed > max_downspeed:
							max_downspeed = down_speed

						up_speed = product.get('uploadSpeed').get('speed')
						if product.get('uploadSpeed').get('uom') == 'Mbps':
							pass
						elif product.get('uploadSpeed').get('uom') == 'Kbps':
							up_speed = float(up_speed/1000)
						else:
							print('NON MBPS/KBPS HERE: ' + address.fullAddress())
							return {
								70 : CoverageResult(is_covered=32),
								10 : CoverageResult(is_covered=32),
								50 : CoverageResult(is_covered=32),
							} 
						if up_speed > max_upspeed:
							max_upspeed = up_speed

				if coverages[10].is_covered in [COVERED_EXISTS, COVERED_NOT_EXISTS]:
					coverages[10].down_speed = max_downspeed
					coverages[10].up_speed = max_upspeed
				if coverages[50].is_covered in [COVERED_EXISTS, COVERED_NOT_EXISTS]:
					coverages[50].down_speed = max_downspeed
					coverages[50].up_speed = max_upspeed

			'''
			# Fixed wireless speeds : Currently, not functioning correctly
			if coverages[70].is_covered == COVERED_GENERAL:

				url = 'https://www.att.com/idp/sales/orchestration/v1/availability/address?_=1583769708466&prevAddressId=00001DXNAF&addressLine1=110%20Debbie%20Ln&zip=72102'
				headers = {
					'accept': 'application/json, text/plain, */*',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					'referer': 'https://www.att.com/shop/service/offers/',
					'sec-fetch-dest': 'empty',
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					'user-agent': user_agent,
				}
				r = s.get(url=url, headers=headers, proxies=proxies)

				response = r.json()
				pp.pprint(response)

				url = 'https://www.att.com/shop/service/offers/'
				headers = {
					'Referer': 'https://www.att.com/shop/address/',
					'Sec-Fetch-Dest': 'document',
					'Upgrade-Insecure-Requests': '1',
					'User-Agent': user_agent,
				}
				r = s.get(url=url, headers=headers, proxies=proxies)

				soup = BeautifulSoup(r.text, "html.parser")

				if debug == True:
					print(str(soup.title))
					print(soup.prettify())

				url = 'https://www.att.com/idp/sales/orchestration/v1/offers/initial?_=1583769808566&requireTV=false&requireHsia=false&requireFwi=true&requireVoip=false&language=english'
				headers = {
					'accept': 'application/json, text/plain, */*',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					'referer': 'https://www.att.com/shop/service/offers/',
					'sec-fetch-dest': 'empty',
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					'user-agent': user_agent,
				}
				r = s.get(url=url, headers=headers, proxies=proxies)

				response = r.json()
				pp.pprint(response)
			'''

			return coverages

		# ISP: Cable One
		elif isp == 'cable_one':
			raise Exception(EXCEPTION_MESSAGE)
			url = "https://publicservices.cableone.net/shoppingcart/api/HomesPassed/Search?street=" + address.line1 + "&apt=" + address.line2 + "&zip=" + address.zipcode + "&manual=false&cartType=CAB&session=ab5acde4-198b-8255-4907b531"
			
			r = requests.get(url = url)
			response = r.json()

			serviceability = not response.get("data").get("isNotServiceable")

			return serviceability

		# ISP: CenturyLink: 
		elif isp == 'centurylink':
			requests.packages.urllib3.disable_warnings() 
			s = requests.session()

			# 1. Get addressId
			url = 'https://geoamsrvcl.centurylink.com/geoam/addressmatch/addresses?q=' + address.fullAddress()

			headers = {
				'Accept':'application/json, text/plain, */*',
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
				'Host': 'geoamsrvcl.centurylink.com',
				'Referer': 'https://www.centurylink.com/home/',
			}

			r = s.get(url=url, headers=headers, verify=False, proxies=proxies)
			result = r.json()

			if debug == True:
				pp.pprint(result)

			address_id = ''
			if result.get('responseCode') == 200:
				for recommended_address in result.get('responseData').get('addresses'):
					if address.line1 in recommended_address.get('fullAddress') and address.zipcode in recommended_address.get('fullAddress'):
						address_id = recommended_address.get('id')

			if debug == True:
				print("Address Id: " + address_id)

			address_for_url = address.line1.replace(" ", "+") + "," + address.city.replace(" ", "+") + "," + address.state + "+" + address.zipcode + ",USA"
			

			url = 'https://shop.centurylink.com/MasterWebPortal/freeRange/login/shop/addressAuthentication?form.addressID=' + address_id + '&form.authType=ban&form.newShopAddress=true&form.pageType=page&form.singleLineAddress=' + address_for_url + '&form.unitNumber='

			headers = {
				'Accept':'application/json, text/plain, */*',
				'Origin':'https://shop.centurylink.com',
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
			}

			r = s.post(url=url, headers=headers, proxies=proxies, verify=False)

			soup = BeautifulSoup(r.text, "html.parser")

			if debug == True:
				print(str(soup.title))
				print(soup.prettify())

			availability = str(soup.title)

			if 'Customize' in availability:
				coverage_result =  CoverageResult(is_covered = COVERED_GENERAL)
			elif 'Out of Region Services' in availability:
				if data == None:
					data = 0
					coverage_result = self.make_request(isp=isp, address=address, debug=debug, proxy=proxy, retries=retries, data=data)
				elif data < 1:
					coverage_result = self.make_request(isp=isp, address=address, debug=debug, proxy=proxy, retries=retries, data=data+1)
				else:
					coverage_result = CoverageResult(is_covered = NOT_COVERED)
				return coverage_result
			elif 'Authentication' in availability:

				# This means one of two things.
				# 1) They requested a unit (so this is a building), and we pick on arbitrarily.
				# 2) They don't recognize the address and are giving alternatives. Let's find out which one
				prompt = soup.find("", {"class": "blockSpan"})

				# In this case, it's likely they're requesting an apt number. We select an option where we "don't know one" (hard to figure this one out so we just store as is for now)
				if prompt == None:
					prompt = soup.find("div", {"id": "UnitNotSelectedErrorMessage"})
					if prompt != None:
						prompt = prompt.text
						if ('Please enter your unit number' in prompt and retries < 3) and data != 'ghostAddress':

							url = r'https://shop.centurylink.com/MasterWebPortal/freeRange/login/shop/addressAuthentication?cx=true&form.iapToken=%24iapToken&form.streetAddress1=' + address.line1.replace(' ','+') + \
							'&form.unitNumber=&form.city=' + address.city + '&form.addressState=' + address.state + f'&form.addresszip={address.zipcode}&form.preAuthentication=true&form.pageType=page&form.authType=ban&form.state={address.state}&form.selectaddress=false&form.eventName=&form.flowType=ghostAddress&form.secUnitID=&form.addressID={address_id}&form.billingSource=CTL&form.typeOfCTAM=ctap'
							r = s.post(url=url,headers=headers,proxies=proxies)

							soup = BeautifulSoup(r.text, "html.parser")

							if debug == True:
								print(str(soup.title))
								print(soup.prettify())

							availability = str(soup.title)

							if 'Customize' in str(soup.title):
								coverage_result = CoverageResult(is_covered=COVERED_GENERAL)
							elif 'Contact Us' in availability:
								return CoverageResult(is_covered=RESPONSES['centurylink']['CONTACT_US'])
							else:
								return CoverageResult(is_covered=UNKNOWN+3)
						else:
							return CoverageResult(is_covered=UNKNOWN+4)
					else:
						# Case of prompt: We're sorry. No match was found in our records for the address as it was entered.
						prompt = soup.find("span", {"id": "formInfo"}).text
						if 'the address you entered is not recognized' in prompt:
							return CoverageResult(is_covered=NOT_RECOGNIZED)
				else:
					prompt = prompt.text

					# 1) Address isn't recognized
					if 'Please select from the list of addresses below' in prompt:

						suggested_addresses = soup.findAll("label", {"id": "fieldFont"})

						# Probably overkill, but going through each suggested address to make sure none match ours
						for suggested_address in suggested_addresses:
							if address.line1 in suggested_address.text and address.zipcode in suggested_address.text:
								return CoverageResult(is_covered = -65)
						return CoverageResult(is_covered = NOT_RECOGNIZED)
					else:
						prompt = soup.find("p", {"id": "formInfo"}).text

						# 2) It's a building so need to get apartment
						if 'We need some additional information' in prompt:
							# This means they requested a unit, so it is a building. Below, we get the name of a unit and then
							# use the unit # in the response 
							requests.packages.urllib3.disable_warnings() 

							# First, get the name of one of the units
							apt_suggestions = soup.find("div", {"class": "mduOptions"})
							apt_clean = ""

							if debug == True:
								print("Apt suggestions: ")
								pp.pprint(apt_suggestions)
								print(type(apt_suggestions))

							apt_clean = ''
							for apt_unclean in apt_suggestions.select('label'):
								apt_clean = re.sub(r'\W+ +', '', apt_unclean.string).upper()
								break

							event_name = ''
							for input_ in apt_suggestions.select('input'):
								event_name = input_['value'].upper()
								break

							unit_id = event_name[len(event_name)-1:]

							if debug == True:
								print('EVENT NAME: ' + event_name)


							url = 'https://shop.centurylink.com/MasterWebPortal/freeRange/login/shop/addressAuthentication?form.addressID=' + address_id + '&form.addressState=' + address.state + '&form.addresszip=' + address.zipcode + '&form.authType=ban&form.city=' + address.city + '&form.eventName=' + event_name + '&form.flowType=secUnitNearMatch&form.pageType=page&form.preAuthentication=true&form.secUnitID=' + unit_id + '&form.selectedAddress=true&form.state=' + address.state + '&form.streetAddress1='+ address.line1 + '&form.unitNumber=' + apt_clean

							headers = {
								'Host': 'shop.centurylink.com',
								'Connection': 'keep-alive',
								'Content-Length': '0',
								'Accept': 'application/json, text/plain, */*',
								'Origin': 'https://shop.centurylink.com',
								'Sec-Fetch-Site': 'same-origin',
								'Sec-Fetch-Mode': 'cors',
								'Referer': 'https://shop.centurylink.com/MasterWebPortal/freeRange/shop/guidedShoppingStart?bones',
								'Accept-Encoding': 'gzip, deflate, br',
								'Accept-Language': 'en-US,en;q=0.9',
							}

							r = s.post(url=url, headers=headers, proxies=proxies)
							soup = BeautifulSoup(r.text, "html.parser")

							if debug == True:
								print('-------------')
								print(soup.prettify())

							if 'Customize' in str(soup.title):
								coverage_result = CoverageResult(is_covered=COVERED_GENERAL)
							else:
								# Unique signifier so if we ever get here, I can figure out what this response means. 
								# My guess is we'll never get, and that if the building wasn't covered at all, we'd get a 0 earlier
								coverage_result = CoverageResult(is_covered=-60)
						else:
							coverage_result = CoverageResult(is_covered=-61)
			elif 'Sorry' in availability:
				if retries < 3:
					return self.make_request(isp, address, debug, proxy, retries+1)
				else:
					coverage_result = CoverageResult(is_covered=UNKNOWN+1)
			elif 'Contact Us' in availability:
				return CoverageResult(is_covered=RESPONSES['centurylink']['CONTACT_US'])
			else:

				prompt = soup.find("div", {"id": "mainoffer"})#.text	

				if 'We are temporarily experiencing system issues' in prompt.p.text:
					return CoverageResult(is_covered=RESPONSES['centurylink']['SYSTEM_ISSUES'])
				if retries < 3:
					return self.make_request(isp, address, debug, proxy, retries+1)
				else:
					coverage_result = CoverageResult(is_covered=UNKNOWN)
				

			if coverage_result.is_covered in [COVERED_GENERAL]:
				
				url = 'https://shop.centurylink.com/MasterWebPortal/qCmsRepository/FreeRange/shop/secure/bones/choice/choice.shopData.vm'

				headers = {
					'Host': 'shop.centurylink.com',
					'Connection': 'keep-alive',
					'Content-Length': '0',
					'Accept': 'application/json, text/plain, */*',
					'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
					'Origin': 'https://shop.centurylink.com',
					'Sec-Fetch-Site': 'same-origin',
					'Sec-Fetch-Mode': 'cors',
					'Referer': 'https://shop.centurylink.com/MasterWebPortal/freeRange/shop/guidedShoppingConfig?bones',
					'Accept-Encoding': 'gzip, deflate, br',
					'Accept-Language': 'en-US,en;q=0.9',
				}

				r = s.post(url=url, headers=headers, proxies=proxies)

				result = r.json()

				if debug == True:
					pp.pprint(result)

				# Confirm it's the correct address. We make the speed -1 for now, but it seems like there might be other endpoints we can use.
				returned_address = result.get('serviceAddress')
				if returned_address.get('streetAddr') != address.line1  or returned_address.get('zip') != address.zipcode:
					return CoverageResult(is_covered=RESPONSES['centurylink']['ADDRESS_MISMATCH'])

				# This handles a weird issue where the API returns that the address is covered, but it isn't actually when
				# you do it online. The way to check seems to be if the max speed is 0. We mark this one differently due to the
				# strange nature and because the resulting prompt seems to imply there is some kind of internet (not high-speed)
				# if you call a number
				if result.get('maxDownProductDescription') == '' and int(result.get('maxDownSpeed')) == 0:
					return CoverageResult(is_covered=RESPONSES['centurylink']['NOT_COVERED_CALL'])

				max_down_product = result.get('maxDownProductDescription').split(' ')
				coverage_result.down_speed = max_down_product[0]

				# Another weird edge case where the API returns that it's covered, but it isn't on the website, presumabely
				# because the speed is so low (in Kbps)
				speed_type = max_down_product[1]
				if speed_type == 'Kbps':
					return CoverageResult(is_covered=RESPONSES['centurylink']['NOT_COVERED_KBPS'])

				return coverage_result
				
			else:
				return coverage_result

		# ISP: Charter Communications (Spectrum/formerly Time Warner)
		elif isp == 'charter':
			if data == None:
				from UserAgents import user_agents_charter
				user_agent = random.choice(user_agents_charter)
			else:
				user_agent = data
			
			s = requests.session()

			url = 'https://buy.spectrum.com/buyflow/buyflow-localization?'
			headers = {
				'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
				#cookie: JSESSIONID=Bq-yXJJagVSo1fVbazyJjiGM.sc58lecabp17_2; affiliate={"v":"118746","barAndRestaurant":false,"cbo":false,"911":false,"tos":false,"mso":"","originatingFlowId":"118746","ID":"118746-CHTR","loc":true}; MINIFY=true; ADRUM_BT=R:0|g:c1def817-1326-4390-a410-20d39c10bbc3924|n:customer1_be398b89-8a00-43fd-886f-ad94f836b86e|i:424575|d:307|e:137; BIGipServer~Eco_102~Spectrum.com-PB-HTTPS=!OZIXpuBcF1dirO6qISkXzcQXGFJmArmhsNWvg79sgmzrJS8FR8xezKG3UsLFzgRFYJgUPm2lkmcV/U0VZHeG2NzlIPTJ5B48VtnIblSUEQ8=; TS014393c9=01c9906dbc371eee95a63dddefca66443121f8540c2888ca06e69375a0e1029070f6b8e77bf3660c672c381260319cf3accd7dc69c734475d89899f6d5b938425b7df6d0e9626ebcbf4fe624b60ae54bba9cdf88a0609c2247f8de9b8207549c7a44ac9b81d75537679bb8c6c7342ca50688c62b65e1776e69559ee7a9c9f532e8ba0af9107632d937e872b1e8c92074b69ec374cb; AKA_A2=A; bm_sz=14D819F39B686500EA939431470EF39A~YAAQ3UlyaLqdfORzAQAAmnUtKAhJ0vI6MiIqvgVB38lxc/gJEM1QaZBRsev/rMG1VzImwHAmB2LOHU9t6pP5pmI9Rz5vAFtpAThQINXuJZpPVhKnNrMIOfRfK19BHmlKF+qeqwdIKg6L/g0lwcQZVd/o6AI1Ap3aAT37fYWoyY1z6Mvdw9sP/Y1TGAOufQtyTBw=; _abck=B33C8DBC4DD3A52EF16CC211C989D111~-1~YAAQ3UlyaLudfORzAQAAmnUtKARLPTmn9QfmdbNy+b3B+OvcCrstynRxjyg6r5AipT+77Rttno6hetPnv72KDdhXbdpuMIfR3NDG5IYbTpB19l/I/aG/agdxalANaAuF9MbvEkHWVgwoLjIq1xDhUS6Dy4LdZ7f52/m70peoRO4Eef7XbUfYyQigctz2b6tIDvt8ZQ2xZyqezfUH1IBEt2Vs3VWJCkeY6Y/MPX7s51M8o+u/6t3/KGscN+zYR1nEdCapG1Pu3LjHT5GHc3aTDxX2fZZoqh6ER7izlsYKbH8vz6Pne6RnkkhkBqU=~-1~-1~-1; ak_bmsc=D3BAD0C91748F61C804416CAE448C37D687249DDAF3500006DAD455FA7D2E153~plgM4Cgby9pL0RPZvMXtEdfc8tOqMu/WggVJq+63kWhz5Px9sEmeZwzJfH3qN7HnJtKU0n8B/UUDHAYx1pv2orYoNKQWJ5dZ/kaMk+H3XroClFXEYt/Ncvxtch3WP3W+l+3s/xPLYKTRsjmMIwzjyFq4JYCSWnndFcVJOo+20/36p5YgPukkXbuNxibR5qeEqQtKZcDshWDxB+KRaADeAuG7vKNoeS1ug7o7CJXzpNH7JNKEFORxqJEBachpDVMgesL4puE9TKo1qUUtaU8M2x6ov6zsNdNdHdVRFz+Kv9O79vcT6XYhjgY+29ewizp+sVh3gH5914DUq2lx7yeBqC0CXdX+4qxpzQLMeBrBCvWy0443iBMNpHvIPts56VAhAh; mbox=check#true#1598401985|session#1598401924898-613022#1598403785; AMCV_97C902BE53295FC80A490D4C%40AdobeOrg=T
				'referer': 'https://buy.spectrum.com/buyflow/buyflow-localization?v=118746',
				'sec-fetch-dest': 'iframe',
				'sec-fetch-mode': 'navigate',
				'sec-fetch-site': 'same-origin',
				'upgrade-insecure-requests': '1',
				'user-agent': user_agent,
			}
			r = s.get(url=url, headers=headers)

			line1_for_url = address.line1.replace(" ", "+")
			line2_for_url =  '' 
			headers = {
				'accept': 'application/json, text/plain, */*',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
				'referer': 'https://buy.spectrum.com/buyflow/buyflow-localization?expiration=session',
				#'cookie': r'MINIFY=true; BIGipServer~Eco_102~Spectrum.com-PB-HTTPS=!SH1UDf2kbBUoU+WlDaBJhgK1RqpX9h6hApXZGpzB3hFDEB47NdkXPUTIxynsHUMu+NW4bcTP8Az7uiOZIEkEK3H2kH/6X8B8XZ6QS16KEQo=; _abck=C646005FF8AF5CF0556E775A3FD77CA2~0~YAAQdgbSFziMKRFzAQAA0qFLIQT2uPYoUCpuFPxHtxIFTLBIg/Xfw2vctyV65dQxwFLKyJ/gP2JnjErvOtR8PE9RXlVkD5q7DUzaKbGjl6jwBPZkppstbw/i0fePgjF41Vtbc/gsf/xaVYC4BB49lMvXPzuVJywe3aAEyB3k1zsyzJiZnfe5CD5Vak8JP/K/ivX9trKdAWw9j781qt66mA/I3amtLkta9QsM6RIOEyyEl56OoM9TAn768nWncjCA8rKX16xlkWP3LhiPuIdlHkILUZwZ58yuhYMdNKRMhNn/n3as2kaL10g57ert+dMbKRA7n6eJbq7L~-1~-1~-1; affiliate=118746; gclid=undefined; s_cc=true; com.silverpop.iMAWebCookie=309ac869-970d-3ebe-37ea-b999504c8c51; _gcl_au=1.1.1437326256.1593991473; _fbp=fb.1.1593991473261.1835131437; aam_uuid=51230999057439989541745199821450114878; BIGipServer~Eco_102~Spectrum.com-PA-HTTPS=!g7uxuXXO4W+of0+qISkXzcQXGFJmAqC/d1DvZv90FVc3Uqx1Zpf1SpRcfoKFeMnMs9kA95KZurvTzuFvuQxyzzqeS6Og392edxV1fYyPF5I=; AMCVS_97C902BE53295FC80A490D4C%40AdobeOrg=1; UA_INFO="{\"browser\":\"Chrome\",\"browser_ver\":\"84.0.4147.105\",\"os\":\"Mac OS X\",\"height\":900,\"width,\":1440}"; userPrefLanguage=en_US; ajs_user_id=null; ajs_group_id=null; ajs_anonymous_id=%224f24a3f1-32cd-43c0-99b7-c21cb90f7ce8%22; DYN_USER_ID=p2u340399622; DYN_USER_CONFIRM=c64a9f0fa227db78cc6f2fa2a7e53c2d; chr-cookie-address={"zipCode":"27410","address1":"2205 NEW GARDEN RD","address2":"APT MAINT"}; cmp=SmartMove_Widget; JSESSIONID=c7nMl+Q7aFqiMZmX9Lv+8qR4.sc58lecabp15; AKA_A2=A; bm_sz=EB08FD33D8E36FF5913D6117D1D31FC2~YAAQ0PtDF3Pa0epzAQAAciuFHgga9qdTmAhLi0E/zQ4uXE4rQIHa+6X865FnEkJKrBaHKKuW5yeXIUZfNWSNM28oW588ORjpjslqdkYCWjx7YJhL1xMxA6sIm7ms0YVG2ylk+k/eHl5w847u5DfsKoBU3LxoQWJQWcj/tze8avy+4hYJ27BX/vldTB6FeqTh2A==; mbox=check#true#1598239939|session#1598239878390-603180#1598241739; affiliate="{\"v\":\"118746\",\"barAndRestaurant\":false,\"cbo\":false,\"911\":false,\"tos\":false,\"mso\":\"\",\"originatingFlowId\":\"118746\",\"ID\":\"118746-CHTR\",\"loc\":true}"; bm_mi=C8D56B3E1A3E3BFA31A90C6EABAE28C8~7znJ5MRfjnEhQ/5HegpbjKO7pl6nsvVOigQzp4FfWtyBMoaiZEp0cnVAQEpLofdRJQmB+v1tXWBH8gSbkpLePyyyu2EPEr30p0jchDLocVtMp7buK0aJ20mgRhtIELCLnXqwIvgOOqeO/bWrUY8yB+s2wPKies85sX365khFLGo9nVf+1mBgpYBGcKnxnTnigIpCUOwfFc6UKRE85UaOwRcE7d48Da8bQnvnvZMSCRbFU5Z4f3TSfTzPE/Romyqf5LD7LFGpjaq37T4UpTboAQ==; AMCV_97C902BE53295FC80A490D4C%40AdobeOrg=1999109931%7CMCMID%7C52804850924011032901614774610505431406%7CMCAAMLH-1598844678%7C7%7CMCAAMB-1598844678%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCAID%7CNONE%7CMCIDTS%7C18479%7CMCOPTOUT-1596557805%7CNONE%7CvVersion%7C3.1.2; ak_bmsc=6616A7AAF9C34BEA2FBC23BFC4824D1A1743FBD03B4600008634435F2D12B910~plpqjxG4ALld773easNtzV2fxCeZHIdAhgj6gkjXuROmvqrODgIJw2dZtJUBuleFMBxqkR36EwPOhN9accAB3XS7hWwpBEcgr0kOH6EYP4G6WlM3L5O0FbJH8T39trYY6ILrDt6g5iLvO2rotkPbDmBqIUtmEqZuVBRB4vg2GqQHRt+/bgb0LsiggB3aAGgVIzv7DiGSDYYPt3EE4MqfVC83Yj/X7aoWwR+Lg0hPx97ccaO6sHewYhCz5CHvqJoI3Q; _uetsid=c363a84a9b4feadab252f0a411443a9e; _uetvid=b59afff9c74ac1bf4d7d5a1fc7d362bd; com.silverpop.iMA.session=58441d5b-c189-c918-337e-80527aad6b4b; com.silverpop.iMA.page_visit=1761105212:; bm_sv=4F34F6EB5DBDC7758BBD8A74955185FA~PsUByS0jVdiJDDysWVjypWN+7uNu6MGNQfxCUTPKSNixJKLBZrAR8HYJGhGKAonNoFmAeVYGiOzO1jk3tanEzrqGYmdsTmGEPmhbgiLLtX6F8cgSWKK/IAgKArwBi3TcGkYIvuzfRT+HgjcVKDS0NVUsrHh7Faywn2ScYp/1VDY=; ADRUM_BT=R:0|g:e274c430-7972-48b7-a5e6-f641c19229b01467|n:customer1_be398b89-8a00-43fd-886f-ad94f836b86e|i:208274|d:2|e:343; TS014393c9=01c9906dbc112159363d513c348a6223234bde0e8f9b38ba5625d367fae0530ededf730fdfa74c52d8f3e83eaa9bf37ddc22686b819c51bca90033ba080c281676dfccb9a3fd20dc68bc4049612b77493850f1b853d6304aec327fd059e0fbd918b811ea5b556af88f45383093ff6b26624640d9fff184968123eddc4376aa4c1b5790c7b74a89d093176633938bfeede797537c62cba3c9be6e849c3718734d5179f755904ae86c5e04814a9f515d034689df2d9b9c0718983819eb0fcda37cb538def502cecd469cf374ab369dbddb140237a1dba817e7636d059d1a3e182e1736c7dfb9; s_sess=%20s_ppv%3D100%3B%20s_campaign%3D%2520SmartMove_Widget%3B%20c_m%3Dundefined%2520SmartMove_Widgetwww.xfinity.com%3B%20search_prop18%3DUnifiedExperience%3B%20s_prop20%3Dbrowse%3B; utag_main=v_id:0173214ba544000243658d9c4dd90307800480700093c$_sn:6$_ss:1$_st:1598241690048$_ga:432997081.1593991473$vapi_domain:spectrum.com$dc_visit:6$_pn:1%3Bexp-session$ses_id:1598239879226%3Bexp-session$aam_load:true%3Bexp-session$dcsyncran:1%3Bexp-session$dc_event:2%3Bexp-session$dc_region:us-east-1%3Bexp-session; s_pers=%20s_camapign_cvp%3D%255B%255B%2527%252520SmartMove_Widget%2527%252C%25271597601563505%2527%255D%255D%7C1755367963505%3B%20s_evar46_cvp%3D%255B%255B%2527Paid%252520Non-Search%2527%252C%25271597601563514%2527%255D%255D%7C1755367963514%3B%20s_campaign_cvp%3D%255B%255B%2527%252520SmartMove_Widget%2527%252C%25271597601563517%2527%255D%255D%7C1755367963517%3B%20s_vnum%3D1625527472656%2526vn%253D6%7C1625527472656%3B%20s_previousPage%3Dcom%253Abuyflow%253Alocalization-resp%7C1598241690088%3B%20s_nr%3D1598239890100-Repeat%7C1600831890100%3B%20s_invisit%3Dtrue%7C1598241690113%3B%20s_dayslastvisit%3D1598239890127%7C1692847890127%3B%20s_dayslastvisit_s%3DMore%2520than%25207%2520days%7C1598241690127%3B; s_sq=charterprod%252Ccharterglobal%3D%2526pid%253Dcom%25253Abuyflow%25253Alocalization-resp%2526pidt%253D1%2526oid%253DCONTINUE%2526oidt%253D3%2526ot%253DSUBMIT; RT="z=1&dm=buy.spectrum.com&si=16803aea-be00-4e0e-ab84-4fff23cdeb6a&ss=ke7yra01&sl=2&tt=16e&bcn=%2F%2F17d09918.akstat.io%2F&ld=331&nu=3bb9764133140af0a89a3a6aab78ae8c&cl=9sn',
				'sec-fetch-mode': 'cors',
				'sec-fetch-site': 'same-origin',
				'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36',#user_agent,
			}
			url = "https://buy.spectrum.com/api/serviceabilityaddresses/v1/serviceabilityaddress?line1=" + line1_for_url + "&line2=" + line2_for_url + "&postalCode=" + address.zipcode

			r = s.get(url = url, headers=headers, proxies=proxies,timeout=10)

			if debug == True:
				print(url)
				print(r.status_code)
			response = r.json()
			if debug == True:
				print(url)
				print(r.status_code)
				pp.pprint(response)

			# If the zip code isn't covered, we return that the address is not covered
			if 'devopsMessage' in response:
				if response.get('devopsMessage') == 'Invalid Zip Code':
					#print(user_agent)
					return CoverageResult(is_covered=RESPONSES['charter']['NOT_COVERED_ZIP'])
				else:
					return CoverageResult(is_covered=UNKNOWN+1)

			old_result = None
			matching_address = False
			for address_json in response.get('content'):
				# Confirm address is the same
				if address_json.get('address').get('line1') == address.line1 and address_json.get('address').get('postalCode').split('-')[0] == address.zipcode:
					if (address_json.get('address').get('id') == None or str(address_json.get('address').get('id')) == 0) and address_json.get('address').get('serviceabilityMatch') != 'NONE':
						coverage_result = CoverageResult(is_covered=47)
					matching_address = True

					# Check all options for serviceabilityMatch 
					if address_json.get('address').get('serviceabilityMatch') == 'NONE':
						# Not covered I think
						if address_json.get('services') != None:
							return CoverageResult(is_covered=44)
						if address_json.get('msoLookupMetrics').get('msoLookUpBusinessUnit') in [None, 'NotCalled'] and address_json.get('msoLookupMetrics').get('csvLookUpBusinessUnit') in [None, 'NotCalled']:
							coverage_result = CoverageResult(is_covered=0)
							continue
						elif address_json.get('msoLookupMetrics').get('msoLookUpBusinessUnit') in ['TWC', 'CHTR'] or address_json.get('msoLookupMetrics').get('csvLookUpBusinessUnit') in ['TWC', 'CHTR']:
							coverage_result = CoverageResult(is_covered=RESPONSES['charter']['CALL_TO_VERIFY'])
							continue
						elif address_json.get('msoLookupMetrics').get('msoLookUpBusinessUnit') == 'Comcast':
							coverage_result = CoverageResult(is_covered=0)
							continue
						elif address_json.get('msoLookupMetrics').get('msoLookUpBusinessUnit') == 'Suddenlink':
							coverage_result = CoverageResult(is_covered=0)
							continue
						elif address_json.get('msoLookupMetrics').get('msoLookUpBusinessUnit') == 'Mediacom':
							coverage_result = CoverageResult(is_covered=0)
							continue
						else:
							# I check the below result (identifying it separately at first), and based on testing output it seems to always be not covered
							coverage_result = CoverageResult(is_covered=0)
							continue

					elif address_json.get('address').get('serviceabilityMatch') == 'Actual':

						# based on maual testing, lineOfBusinessServiceability appears to be the determinative field (and not 'services')
						if address_json.get('lineOfBusinessServiceability') == None:
							if address_json.get('serviceStatus') == 'Active':
								coverage_result = CoverageResult(is_covered=50)
							elif address_json.get('serviceStatus') == 'Former':
								coverage_result = CoverageResult(is_covered=51)
							elif address_json.get('serviceStatus') == 'NONE':
								coverage_result = CoverageResult(is_covered=RESPONSES['charter']['NO_SERVICE_STATUS_VERIFY'])
							elif address_json.get('serviceStatus') == 'Never':
								coverage_result = CoverageResult(is_covered=RESPONSES['charter']['NEVER_SERVICE_STATUS'])
							else:
								coverage_result = CoverageResult(is_covered=52)
						else:
							# Get lines of business
							lines_of_business = dict()
							for line in address_json.get('lineOfBusinessServiceability'):
								lines_of_business[line.get('name')] = line.get('serviceable')
							
							if 'Digital' in lines_of_business or 'DIGITAL' in lines_of_business:
									coverage_result = CoverageResult(is_covered=103)

							if lines_of_business.get('HSD') == True:
								coverage_result = CoverageResult(is_covered=COVERED_GENERAL)
							elif lines_of_business.get('HSD') == False:
								coverage_result = CoverageResult(is_covered=RESPONSES['charter']['NOT_COVERED_HSD_FALSE'])
							else:
								if lines_of_business.get('I') == True or lines_of_business.get('T') == True:
									coverage_result = CoverageResult(is_covered=COVERED_GENERAL)
								else:
									coverage_result = CoverageResult(is_covered=UNKNOWN+5)

							'''
							# Ran some manual tests just to see when 'services' indicates services where 'lineOfBusinessServiceability' says there's not
							# In these cases on the spectrum website, there was no service. So again seems like lineOfBusinessServiceability is the determinative field.
							if coverage_result.is_covered == RESPONSES['charter']['NOT_COVERED_HSD_FALSE']:
								for services in address_json.get('services'):
									if services.get('description') == 'HSD' and services.get('available') == True:
										coverage_result = CoverageResult(is_covered=38)
							'''

					elif address_json.get('address').get('serviceabilityMatch') == 'Zip+4':
						if address_json.get('lineOfBusinessServiceability') == None:
							coverage_result = CoverageResult(is_covered=RESPONSES['charter']['NOT_COVERED_ZIP4'])
						else:
							coverage_result = CoverageResult(is_covered=UNKNOWN+2)

					else:
						coverage_result = CoverageResult(is_covered=UNKNOWN+6)
					
					# Often in a building the n/a unit has no coverage when other ones do, so don't return if this is an n/a unit (if there's a non n/a unit we can choose)
					if address_json.get('address').get('line2') == None:
						# Sometimes there are two n/a units, if so, we return whichever is covered, or if neither the original one
						if old_result == None:
							old_result = coverage_result
						else: #elif old_result.is_covered != RESPONSES['charter']['NOT_COVERED_HSD_FALSE']:
							if old_result.is_covered != RESPONSES['charter']['NOT_COVERED_HSD_FALSE']:
								coverage_result = old_result
							elif coverage_result.is_covered != RESPONSES['charter']['NOT_COVERED_HSD_FALSE']:
								pass
							else:
								coverage_result = old_result
						continue
					else:
						break
				else:
					continue
			if matching_address == False:
				coverage_result = CoverageResult(is_covered=RESPONSES['charter']['NO_MATCHING_ADDRESS'])

			return coverage_result


		# ISP: Cincinnati
		elif isp == 'cincinnati':
			raise Exception(EXCEPTION_MESSAGE)

			url = 'https://www.cincinnatibell.com/api/identification/new'

			headers = {
				'Accept':'application/json, text/plain, */*',
				'Origin':'https://www.cincinnatibell.com',
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
				'Content-Type':'application/json;charset=UTF-8',
			}

			body = {
				"address": {
					"said":'null',
					"formattedAddress": address.line1 + ", " + address.city + ", " + address.state + " " + address.zipcode,
					"formattedLine1":address.line1,
					"formattedLine2": address.city + ", " + address.state + " " + address.zipcode,
					"formattedAddress2":"",
					"isAptUnitRequired":'false',
					"streetNumber":"1781",
					#"streetName":"Carll",
					"streetPreDirection":'null',
					"streetPostDirection":'null',
					#"streetSuffix":"St",
					"secondaryDesignator":'null',
					"secondaryNumber":'null',
					"cityName":address.city,
					"state":address.state,
					"zipCode":address.zipcode,
					#"plus4Code":"1939"
				},
				"emailAddress":"",
				"primaryPhone":"",
				"firstName":"",
				"lastName":"",
				"customerType":"Consumer"
			}

			r = requests.post(url=url, json=body, headers=headers)
			response = r.json()
			print(response)

		# ISP: Consolidated
		elif isp == 'consolidated':

			s = requests.session()
			requests.packages.urllib3.disable_warnings() 
			
			# Check zipcode

			url = 'https://www.consolidated.com/DesktopModules/Consolidated/API/Address/GetZipCodeDetail?zipCode=' + address.zipcode
			headers = {
				'Accept': 'application/json, text/plain, */*',
				'Accept-Encoding': 'gzip, deflate, br',
				'Accept-Language': 'en-US,en;q=0.9',
				'Connection': 'keep-alive',
				'Content-Length': '0',
				'Content-Type': 'application/json;charset=utf-8',
				'Host': 'www.consolidated.com',
				'Origin': 'https://www.consolidated.com',
				'Referer': 'https://www.consolidated.com/',
				'Sec-Fetch-Dest': 'empty',
				'Sec-Fetch-Mode': 'cors',
				'Sec-Fetch-Site': 'same-origin',
				'User-Agent': user_agent,
			}
			r = s.post(url = url,headers=headers, proxies=proxies, verify=False)
			response  = r.json()

			if debug == True:
				pp.pprint(response)

			if response.get('success') == False:
				if 'Zip Code not found' in response.get('message'):
					return CoverageResult(is_covered=RESPONSES['consolidated']['NOT_COVERED_ZIP'])
				else:
					return CoverageResult(is_covered=30)

			# Get Address ID
			url = 'https://www.consolidated.com/DesktopModules/Consolidated/API/Address/GetAddressSearch?search=' + address.line1

			address_id = ''
			headers = {
				'Accept': 'application/json, text/plain, */*',
				'Accept-Encoding': 'gzip, deflate, br',
				'Accept-Language': 'en-US,en;q=0.9',
				'Connection': 'keep-alive',
				'Content-Length': '0',
				'Content-Type': 'application/json;charset=utf-8',
				'Host': 'www.consolidated.com',
				'Origin': 'https://www.consolidated.com',
				'Referer': 'https://www.consolidated.com/residential/internet/order-internet',
				'Sec-Fetch-Dest': 'empty',
				'Sec-Fetch-Mode': 'cors',
				'Sec-Fetch-Site': 'same-origin',
				'User-Agent': user_agent,
			}
			r = s.post(url = url, headers=headers, proxies=proxies, verify=False)
			response = r.json()

			if debug == True:
				pp.pprint(response)

			if response.get('success') == False:
				if 'Address not found.' in response.get('message'):
					return CoverageResult(is_covered=RESPONSES['consolidated']['ADDRESS_NOT_FOUND'])
				else:
					return CoverageResult(is_covered=31)

			# Check if our address is in returned address, and return error if there is no matching
			for address_json in response.get('result'):
				if address.line1 in address_json.get('Address') and address.city in address_json.get('Address') and address.state in address_json.get('Address'):
					address_id = address_json.get('AddressId')
					break  
			if address_id == '':
				return CoverageResult(is_covered=RESPONSES['consolidated']['NO_MATCHING_ADDRESS'])

			if debug == True:
				print('ADDRESS_ID: ' + str(address_id))

			# Get coverage info with address id
			url = 'https://www.consolidated.com/DesktopModules/Consolidated/API/Address/GetAddressDetails?addressId=' + address_id
			headers = {
				'Accept': 'application/json, text/plain, */*',
				'Accept-Encoding': 'gzip, deflate, br',
				'Accept-Language': 'en-US,en;q=0.9',
				'Connection': 'keep-alive',
				'Content-Length': '0',
				'Content-Type': 'application/json;charset=utf-8',
				'Host': 'www.consolidated.com',
				'Origin': 'https://www.consolidated.com',
				'Referer': 'https://www.consolidated.com/residential/internet/order-internet',
				'Sec-Fetch-Dest': 'empty',
				'Sec-Fetch-Mode': 'cors',
				'Sec-Fetch-Site': 'same-origin',
				'User-Agent': user_agent,
			}
			r = s.post(url = url, headers=headers, proxies=proxies, verify=False)
			response = r.json()

			if debug == True:
				print(url)
				pp.pprint(response)

			if response.get('success') == True:
				control_number = response.get('result').get('ControlNumber')
				coverage_result =  CoverageResult(is_covered=COVERED_GENERAL)
			else:
				return CoverageResult(is_covered=32)
			if debug == True:
				print('CONTROL NUMBER: ' + str(control_number))
			if control_number == None or control_number == '':
				return CoverageResult(is_covered=RESPONSES['consolidated']['NO_CONTROL_NUM'])

			url = 'http://www.fairpoint.com/home/residential/offers/featured-offers.FeatureOffersAction.do'
			data = {
				'eulId': control_number,
				'groupname':'', 
				'segment': 'Residential',
				'type': 'customerValidation',
				'location': address.state,
			}
			headers = {
				'Accept': 'application/json, text/javascript, */*; q=0.01',
				'Accept-Encoding': 'gzip, deflate',
				'Accept-Language': 'en-US,en;q=0.9',
				'Connection': 'keep-alive',
				'Content-Length': '81',
				'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
				'Host': 'www.fairpoint.com',
				'Origin': 'http://www.fairpoint.com',
				'Referer': 'http://www.fairpoint.com/home/residential/offers/featured-offers.html',
				'User-Agent': user_agent,
				'X-Requested-With': 'XMLHttpRequest',
			}
			r = s.post(url = url, data=data, headers=headers,proxies=proxies, verify=False)
			response = r.json()

			if debug == True:
				pp.pprint(response)

			services = response.get('response')[0].get('serviceDetails').get('service')

			max_downspeed = -1
			max_upspeed = -1
			for service in services:
				for bundle in service.get('bundleDetails'):
					speed = bundle.get('internet').get('name')

					speed_list = speed.split('/')
					if len(speed_list) != 2:
						continue

					if 'K' in speed_list[0]:
						down_speed = float(speed_list[0].replace('K','')) / 1000
					else:
						down_speed = float(speed_list[0].replace('M',''))
					if down_speed > max_downspeed:
						max_downspeed = down_speed
					if 'K' in speed_list[1]:
						up_speed = float(speed_list[1].replace('K','')) / 1000
					else:
						up_speed = float(speed_list[1].replace('M','')) 
					if up_speed > max_upspeed:
						max_upspeed = up_speed

			coverage_result.down_speed = max_downspeed
			coverage_result.up_speed = max_upspeed

			# if there is no internet speed using the above method, that means internet isn't offered as an option
			# the house isn't covered
			if str(coverage_result.down_speed) == '-1' and str(coverage_result.up_speed) == '-1':
				return CoverageResult(is_covered=NOT_COVERED)

			return coverage_result

		#ISP: Cox
		elif isp == 'cox':

			s = requests.session()
			url = 'https://www.cox.com/webapi/aem/addressserviceability'

			headers = {
				'Accept':'application/json, text/javascript, */*; q=0.01',
				'Origin':'https://www.cox.com',
				'X-Requested-With':'XMLHttpRequest',
				'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36',
				'Sec-Fetch-Mode': 'cors',
				'Content-Type': 'application/json; charset=UTF-8',
				'Cache-Control': 'no-cache',
				'Postman-Token': 'e1e3bd46-c358-47ab-bae8-9a666ac801ce',
				'Host': 'www.cox.com',
				'Accept-Encoding': 'gzip, deflate',
				'Content-Length': '60',
			}

			apt = ''
			if address.apt_number != '':
				if address.apt_type == '':
					apt = address.apt_number
				else:
					apt = address.apt_type + ' ' + address.apt_number

			body = {
				'address': address.line1,
				'zipCode': address.zipcode,
				'apt': apt,
			}

			r = s.post(url=url, json=body, headers=headers, proxies=proxies)
			response = r.json()

			if debug == True:
				pp.pprint(response)

			'''
			# This was a test to see whether we ever get addressMatch = True when serviceable = False (we did not)
			if response.get('serviceable') == False and response.get('addressMatch') == False:
				print(address.fullAddress())
				print(response)
			'''

			if response.get('serviceable') == True and response.get('addressMatch') == True:
				result = CoverageResult(is_covered = COVERED_GENERAL)
			else:
				if 'errorMessage' in response:
					if 'ADDRESS_ERROR_BUSINESS_ADDRESS' in response.get('errorMessage'):
						result =  CoverageResult(is_covered = BUSINESS)
					elif 'ADDRESS_ERROR_UNSERVICEABLE_ADDRESS' in response.get('errorMessage'):

						# According to Cox, the address is not covered. However, when they do not recognize
						# an address, they simply say they do not cover it. To make sure the address is actually
						# not covered (rather than not recognized), we'll check the following request (which is another
						# service that appears in this case that redirects to a different provider).
						
						url = 'https://www.smartmove.us/Widget/WidgetService.asmx/G2BSearch'

						headers = {
							'accept': 'application/json, text/javascript, */*; q=0.01',
							'accept-encoding': 'gzip, deflate, br',
							'accept-language': 'en-US,en;q=0.9',
							#'content-length': '211',
							'content-type': 'application/json; charset=UTF-8',
							'origin': 'https://www.cox.com',
							'referer': 'https://www.cox.com/residential-shop/order-cox-services.cox',
							'sec-fetch-mode': 'cors',
							'sec-fetch-site': 'cross-site',
							'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
						}
						body = {
							'sMSO':'1010',
							'Address': address.line1,
							'Apt':address.apt_type + ' ' + address.apt_number,
							'Zip': address.zipcode,
							'mobile':'false',
							'c':'0',
							'server':'https://www.smartmove.us/', 
							'ReferrerURL':'https://www.cox.com/residential-shop/checkout-profile.cox'
						}

						r = s.post(url=url, json=body, headers=headers, proxies=proxies)
						response = r.json()

						if debug == True:
							pp.pprint(response)

						if "We couldn't find an online match" in response['d'] or 'We need a bit more information' in response['d']:
							result =  CoverageResult(is_covered = NOT_RECOGNIZED)
						else:
							result =  CoverageResult(is_covered = NOT_COVERED)
					elif 'ADDRESS_ERROR_MULTIPLE_ADDRESS_MATCH' in response.get('errorMessage'):
						result = CoverageResult(is_covered = 10)
						
						# There are multiple addresses to choose from. We choose one
						url = 'https://www.cox.com/residential-shop/order-cox-services.cox'

						apt = ''
						if address.apt_number != '':
							if address.apt_type == '':
								apt = address.apt_number
							else:
								apt = address.apt_type + ' ' + address.apt_number

						body = {
							'device-type':'desktop',
							'streetAddress': address.line1,
							'submit':'Continue',
							'unit': apt,
							'zipCode': address.zipcode,
						}

						headers = {
							'Origin':'https://www.cox.com',
							'Upgrade-Insecure-Requests':'1',
							'Content-Type':'application/x-www-form-urlencoded',
							'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36',
							'Sec-Fetch-User':'?1',
							'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
						}

						r = s.post(url=url, data=body, headers=headers, proxies=proxies)

						soup = BeautifulSoup(r.text, "html.parser")

						if debug == True:
							print(soup.prettify())

						options = soup.find("select",{"name":"multiAddressSelect"}).findAll("option")

						apt = ''
						for option in options:
							apt = option.text.split(',')[1]

							if apt[0] == ' ':
								apt = apt[1:]

							# Often the first result is just the building address (which would mean apt is the city. We only select a result
							if address.city not in apt.upper():
								break

						# Now, redo the request with the apartment given to us
						address = copy.copy(address)
						address.apt_type = ''
						address.apt_number = apt

						if retries < 2:
							return self.make_request(isp, address, debug, proxy, retries + 1)
						else:
							return CoverageResult(is_covered = UNKNOWN+1)
						
					elif 'ADDRESS_ERROR_MATCH_THRESHOLD_EXCEEDED' in response.get('errorMessage'):
						result = CoverageResult(is_covered = 10)
						# The list of possible addresses is too large for cox to return, so we're going to try to arbitrarily narrow the list
						
						if data != None and data == 'MAX_THRESHOLD_RETRY':
							return CoverageResult(is_covered = BUILDING_UNKNOWN)

						apt_attempts = ['APT', '1', '3', 'A']

						for apt in apt_attempts:
							address.apt_type = ''
							address.apt_number = apt

							#print("Redoing 2")
							result = self.make_request(isp=isp, address=address, debug=debug, proxy=proxy, data='MAX_THRESHOLD_RETRY')
							if result.is_covered != BUILDING_UNKNOWN:
								return result

						result = CoverageResult(is_covered = BUILDING_UNKNOWN)
						
					elif 'GetContextCommand could not be queued' in response.get('errorMessage'):
						if retries < 2:
							return self.make_request(isp=isp, address=address, debug=debug, retries=retries+1)
						else:
							result =  CoverageResult(is_covered = UNKNOWN+7)
					else:
						result =  CoverageResult(is_covered = UNKNOWN+3)
				else:
					result =  CoverageResult(is_covered = UNKNOWN)
			
			if result.is_covered in [COVERED_GENERAL]:

				# CONFIRM ADDRESS
				url = 'https://www.cox.com/residential-shop/shop.cox'
				r = s.get(url = url, proxies=proxies)

				soup = BeautifulSoup(r.text, "html.parser")

				if debug == True:
					print('--------------------------------------------------------------------------')
					print(soup.prettify())
					print('--------------------------------------------------------------------------')

				# Sometimes this request does not work, and it is backing up progress. For now we'll just save the coverage
				# result without speed and can go back later
				try:
					data = json.loads(soup.find('script', {"class": "templateData"}).text)

					if debug == True:
						print('--------------------------------------------------------------------------')
						pp.pprint(data)
						print('--------------------------------------------------------------------------')

					max_upspeed = -1
					max_downspeed = -1
					for offer in data.get('ShopResponse').get('offerInfos'):
						details = offer.get('keyFeatures')

						offer_downspeed = None
						offer_upspeed = None

						# Get down/upspeed from details
						for detail in details:
							if detail.get('name') == 'DOWNLOAD_SPEED':
								# Offer value is in format 'xx Mpbs' where xx is the value
								offer_downspeed = int(detail.get('value').split(' ')[0])

								if offer_downspeed != None and offer_upspeed != None:
									break

							if detail.get('name') == 'UPLOAD_SPEED':
								# Offer value is in format 'xx Mpbs' where xx is the value
								offer_upspeed = int(detail.get('value').split(' ')[0])

								if offer_downspeed != None and offer_upspeed != None:
									break

						# if down/upspeed is greater than max, it becomes new max
						if offer_downspeed != None and offer_downspeed > max_downspeed:
							max_downspeed = offer_downspeed
						if offer_upspeed != None and offer_upspeed > max_upspeed:
							max_upspeed = offer_upspeed

					result.down_speed = max_downspeed
					result.up_speed = max_upspeed

					return result
				except:
					return result
			else:
				return result
			

		# ISP: Earthlink *need to confirm yes case (need to find good address)
		elif isp == 'earthlink':
			raise Exception(EXCEPTION_MESSAGE)
			url = 'https://cfbbnearthlinkwidget.cfdomains.com/api/search/' + address.line1 + ', ' + address.city + ', ' + address.state + " " + address.zipcode 

			headers = {
				'Sec-Fetch-Mode':'cors',
				'Origin':'https://www.earthlink.net',
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36',
				'Accept':'*/*',
				'Cache-Control': 'no-cache',
				'Postman-Token': '3d65b715-06e4-4a54-b4e2-9e2e550ff054',
				'Host': 'cfbbnearthlinkwidget.cfdomains.com',
				'Accept-Encoding': 'gzip, deflate',
				'Connection': 'keep-alive'
			}

			r = requests.get(url=url, headers=headers)

			response = r.json()

			found_earthlink = False
			speed = -1
			for product in response.get('products'):
				if 'Earthlink' in product.get('providerName'):
					found_earthlink = True
					speed = product.get('downloadSpeed')

			if found_earthlink == True:
				return CoverageResult(is_covered=True, speed=speed)
			else:
				return CoverageResult(is_covered=False)

		# ISP: Frontier
		elif isp == 'frontier':

			import string
			#import random
			def randomString(stringLength=8):
			    letters = string.ascii_lowercase
			    return ''.join(random.choice(letters) for i in range(stringLength))

			s = requests.session()

			# See if they find address
			url = f"https://fr-address-detail.integration-services.redventures.io/application/address/suggestions?zip={address.zipcode}&addressline1={address.line1.replace(' ','%20')}"

			r = s.get(url=url, proxies=proxies)
			response = r.json()

			if debug == True:
				pp.pprint(response)

			found_address = False
			for suggested_address in response:
				if suggested_address.get('addressLine1') == address.line1 and suggested_address.get('zip') == address.zipcode:
					found_address = True

			# Get order id
			url = 'https://fr-brand-bff.integration-services.redventures.io/graphql'

			body = {
				"operationName":"CREATE_ORDER_MUTATION",
				"variables": {
					"affiliateId":"RV CART TAG BASE",
					"mcid":"3566206"
				},
				"query":"mutation CREATE_ORDER_MUTATION($affiliateId: String!, $mcid: String!) {\n  createOrder(affiliateId: $affiliateId, mcid: $mcid) {\n    orderId\n    __typename\n  }\n}\n"
			}

			# x-client-session-id needs to be manually replaced with the session id from a manual session with frontier (can't find a way to develop it automatically).
			# Once you do this though, usually it can run for a long while
			headers = {
				'accept': '*/*',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
				#'content-length': '1899',
				'content-type': 'application/json',
				'origin': 'https://frontier.com',
				'referer': 'https://frontier.com/order-online/address',
				'sec-fetch-dest': 'empty',
				'sec-fetch-mode': 'cors',
				'sec-fetch-site': 'cross-site',
				'user-agent': user_agent,
				'x-client-id': 'fr-cart-production',
				'x-client-session-id': 'ad1efc7{}-e5cc-4a{}d-a{}b{}-b{}9b6{}f{}0c{}a'.format(str(random.randint(0,9)),str(random.randint(0,9)),str(random.randint(0,9)),str(random.randint(0,9)),str(random.randint(0,9)),str(random.randint(0,9)),str(random.randint(0,9)),str(random.randint(0,9)),str(random.randint(0,9))),
				#'x-cohesion-anonymous-id': 'fa76416c-f7c0-410e-9dc5-4f1cf28d0935',
				#'x-cohesion-session-id': 'fa76416c-f7c0-410e-9dc5-4f1cf28d0935',
				#'x-correlation-id': '6eec9596-9264-4667-b31c-e3877f13ba63',
				'x-tenant-id': '2646f3b4-2a12-48ac-979d-ad332d8e53a6',
			}

			r = s.post(url=url,headers=headers,json=body,proxies=proxies)

			response = r.json()

			if debug == True:
				print('Create order...')
				pp.pprint(response)

			order_id = response.get('data').get('createOrder').get('orderId')

			body = {
				"operationName":"RUN_SERVICEABILITY_MUTATION",
				"variables": {
					"address1":address.line1,
					"zip":address.zipcode, 
					"state":address.state,
					"city":address.city,
					"orderId":order_id,
				},
				"query":"mutation RUN_SERVICEABILITY_MUTATION($address1: String!, $city: String!, $zip: String!, $orderId: String!, $state: String!, $overrideExistingService: Boolean) {\n  runServiceability(address1: $address1, zip: $zip, orderId: $orderId, city: $city, state: $state, overrideExistingService: $overrideExistingService) {\n    tabKeys\n    segments\n    serviceable\n    existingService\n    serviceablePrediction {\n      fiber\n      default\n      __typename\n    }\n    suggestedAddresses {\n      address1\n      address2\n      city\n      state\n      zip\n      __typename\n    }\n    promotions {\n      promoType\n      name\n      description\n      imageUrl\n      subtext\n      toolTipText\n      legal\n      promoType\n      amount\n      startDate\n      endDate\n      promotionalId\n      source\n      __typename\n    }\n    products {\n      productId\n      name\n      tags\n      priority\n      promotions {\n        name\n        description\n        imageUrl\n        subtext\n        toolTipText\n        legal\n        promoType\n        __typename\n      }\n      features\n      shortLegal\n      legal\n      includedProducts {\n        internet\n        video\n        voice\n        __typename\n      }\n      attributes {\n        downloadSpeed\n        uploadSpeed\n        minChannels\n        maxChannels\n        __typename\n      }\n      pricing {\n        amount\n        amountMajor\n        amountMinor\n        promotionalAmount\n        promotionalAmountMajor\n        promotionalAmountMinor\n        currency\n        currencySymbol\n        duration\n        delay\n        frequency\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"}


			r = s.post(url=url,headers=headers,json=body,proxies=proxies)

			response = r.json()

			data = response.get('data').get('runServiceability')

			if debug == True:
				pp.pprint(data)

			if data.get('serviceable') == True:
				max_downspeed = -1
				max_upspeed = -1


				if data.get('products') != None:
					for product in data.get('products'):
						if product.get('attributes').get('downloadSpeed') > max_downspeed:
							max_downspeed = product.get('attributes').get('downloadSpeed')
						if product.get('attributes').get('uploadSpeed') > max_upspeed:
							max_upspeed = product.get('attributes').get('uploadSpeed')
					if max_downspeed == -1:
						# Returns an error message on BAT UI. In the backend, the address is marked as serviceable but has no speed info. Maybe a bug in the BAT?
						return CoverageResult(is_covered=RESPONSES['frontier']['HAVING_TROUBLE_PRODUCTS'])

				if data.get('existingService') == True:
					coverage_status = COVERED_EXISTS

				elif data.get('existingService') == False:
					coverage_status = COVERED_NOT_EXISTS
				else:
					return CoverageResult(is_covered=UNKNOWN+1)
				return CoverageResult(is_covered=coverage_status, max_downspeed=max_downspeed, max_upspeed=max_upspeed)
			else:
				# Seems to return "service prediction" number. We checked various numbers, and 0.697 seems to be minimum where it returns not covered (0.7027 and above returned the error message, so pretty good lower baseline)

				# Most obviously not covered
				if data.get('serviceablePrediction').get('default') == 0.0 and data.get('serviceablePrediction').get('fiber') == 0.0 :
					coverage_result = CoverageResult(is_covered=NOT_COVERED)	
				# This means we get the "Don't worry - we'll get this sorted out." message
				elif data.get('serviceablePrediction').get('default') > 0.697 or data.get('serviceablePrediction').get('fiber') > 0.697:
					coverage_result = CoverageResult(is_covered=RESPONSES['frontier']['HAVING_TROUBLE'])
				# Returns that the address is not copvered 
				else:
					coverage_result = CoverageResult(is_covered=RESPONSES['frontier']['NOT_COVERED_UNDER'])
				
				if data.get('suggestedAddresses') != None and retries == 0:
					for suggested_address in data.get('suggestedAddresses'):
						 if suggested_address.get('address1') != address.line1:
						 	address.line1 = suggested_address.get('address1')
						 	return self.make_request(isp=isp, address=address,debug=debug, proxy=proxy, retries=1)
					return coverage_result
				return coverage_result
				if found_address == True:
					return CoverageResult(is_covered=NOT_COVERED)
				else:
					return CoverageResult(is_covered=NOT_RECOGNIZED)

		# ISP: Mediacom
		elif isp == 'mediacom':
			raise Exception(EXCEPTION_MESSAGE)
			url = 'https://shop.mediacomcable.com/shop/check'

			headers = {
				'Accept':'application/json, text/javascript, */*; q=0.01',
				'Origin':'https://shop.mediacomcable.com', 
				'X-Requested-With':'XMLHttpRequest',
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36', 
				'Sec-Fetch-Mode':'cors', 
				'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
				'Cache-Control': 'private,no-cache, no-store',
				'Pragma': 'no-cache',
				'Content-Type': 'application/json; charset=utf-8',
				'Expires':'-1',
				'Server': 'Microsoft-IIS/8.5',
				'X-AspNetMvc-Version':'5.2',
				'X-AspNet-Version':'4.0.30319',
				'Set-Cookie':'mcc-sid=MkOwXo79xE-c; expires=Tue, 22-Oct-2019 17:46:32 GMT; path=/; secure; HttpOnly',
				'X-Xss-Protection':'1; mode=block',
				'X-Frame-Options':'SAMEORIGIN',
			}

			body = {
				'Address1': address.line1,
				'UnitNumber':'',
				'Zip': address.zipcode
			}

			r = requests.post(url=url, json=body, headers=headers)
			response = r.json()

			serviceability = response.get('ResponseCode')

			if serviceability == 'ServiceNotOffered':
				return False
			elif serviceability == 'SingleSuccess':
				return True
			else:
				return 'Other'

		# ISP: Optimum
		# 
		elif isp == 'altice':

			user_agent = random.choice(user_agents_ipad)
			user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36'
			s = requests.session()
			if proxies != None:
				s.proxies.update(proxies)

			if True:
				# This doesn't work, doesn't use this API from Optimum home page

				'''
				url = 'https://www.gstatic.com/recaptcha/releases/r8WWNwsCvXtk22_oRSVCCZx9/recaptcha__en.js'
				r = s.get(url=url)

				print(r.status_code)
				#pp.pprint(r.text)
				#return
				'''
				'''
				url = 'https://order.optimum.com/'
				headers = {
					'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					#cookie: __cfduid=d907b046dc2b4bfaf34b22bf4e36cb5b91596128690; phoneUpdate=default; check=true; _gcl_au=1.1.1913751777.1596128692; AMCVS_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1; _fbp=fb.1.1596128692148.1269726582; invoca_session=%7B%22ttl%22%3A%222020-08-29T17%3A04%3A52.244Z%22%2C%22session%22%3A%7B%7D%2C%22config%22%3A%7B%22campaignIdOverrideParam%22%3Anull%2C%22campaignIdOverrideValue%22%3Anull%2C%22requirementsNeeded%22%3Atrue%2C%22ce%22%3Atrue%7D%7D; s_cc=true; _ga=GA1.2.1633463053.1596128694; _gid=GA1.2.1346219299.1596128694; aam_uuid=51230999057439989541745199821450114878; IOTest=tenDollarPhone%3Dfalse%7C; connect.sid=s%3A1-IYvLoH-Ndfc0Y3n2_H-6BKM96p9Crg.NZcUUz1CftI14MBobgwkeoC98HCQBqNZRlSSl%2BV0Zrs; visid_incap_1012317=p6y4JcUkQQK+NBH+zgFmb879Il8AAAAAQUIPAAAAAABLrZn+0w6CYxLjU5mkbnVd; nlbi_1012317=EVA4f0B4gCzXq7XDZZ1JwgAAAAD+vG3npPJIB2LcL3d5J3ex; optimizelyEndUserId=oeu1596128719725r0.06892938416817374; _ga=GA1.3.1633463053.1596128694; _gid=GA1.3.1346219299.1596128694; SnapABugHistory=1#; aam_uuid=51230999057439989541745199821450114878; s_tbe_shop_order=1596129657100; AWSELB=01A95B1D141ABCE2F760790708E7A8CA24904814EC85EC39AA8737EAB7E35B87BAA3575BEBC4AE5481A6A96029DFEDF5416411D67DFB33E6204901A80D2C7F3CCA131A42AB; AWSELBCORS=01A95B1D141ABCE2F760790708E7A8CA24904814EC85EC39AA8737EAB7E35B87BAA3575BEBC4AE5481A6A96029DFEDF5416411D67DFB33E6204901A80D2C7F3CCA131A42AB; incap_ses_702_1012317=kACFUfc5dWrtHU4cdAG+CQEvI18AAAAAHp4lwgE+eO/te5cvbPj8QQ==; SnapABugRef=https%3A%2F%2Forder.optimum.com%2FBuyflow%2FStorefront%20; s_dfa=cablevis-uow-com; s_vnc365=1627677316063%26vn%3D3; s_ivc=true; AMCV_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1075005958%7CMCIDTS%7C18474%7CMCMID%7C51207873653272410511743008777202681743%7CMCAAMLH-1596746116%7C7%7CMCAAMB-1596746116%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1596148517s%7CNONE%7CvVersion%7C4.4.1; bounceClientVisit3324v=N4IgNgDiBcIBYBcEQM4FIDMBBNAmAYnvgPYBOAJgKakB0xECAlgLYCuzNAxsc0QEKsAngDMwxAO5EAygjKVhpYgDsEIADQhSMECAC+QA; s_sq=%5B%5BB%5D%5D; _uetsid=132f762cdc481d782c6006788b2bcaff; _uetvid=30d100605755205f246437df491f5f01; mp_95c15e221f6fe325df9f5b74d815bd35_mixpanel=%7B%22distinct_id%22%3A%20%22173a0af757335e-002d78435f8bbb-31627404-13c680-173a0af75745de%22%2C%22%24device_id%22%3A%20%22173a0af757335e-002d78435f8bbb-31627404-13c680-173a0af75745de%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.optimum.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22www.optimum.com%22%2C%22Referral%20Source%22%3A%20%22SDLCOM%22%2C%22Page%22%3A%20%22%2FBuyflow%2FStorefront%22%2C%22House%20Status%22%3A%20%22SUB%22%2C%22Current%20Customer%22%3A%20false%7D; SnapABugUserAlias=%23; SnapABugVisit=18#1596128721; mbox=PC#12ceebd257f94809a473eb10c070d230.35_0#1659386424|session#ddc95bd83a334e08947b0245ef7a0988#1596143175; _gat_UA-87150803-1=1; s_nr30=1596141625959-Repeat; s_tslv=1596141625960; opt_ev1=%5D%2C%22opt%253Aen%253Aresi%253Abuyflow%253Astorefront%22%5D%221596141625986%22%5B%2C; opt_ppn=opt%3Aen%3Aresi%3Abuyflow%3Astorefront; s_tbe_pros_order=1596141626298
					'sec-fetch-dest': 'document',
					'sec-fetch-mode': 'navigate',
					'sec-fetch-site': 'none',
					'sec-fetch-user': '?1',
					'upgrade-insecure-requests': '1',
					'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
				}
	
				r = s.get(url=url,headers=headers)
				
				url = 'https://order.optimum.com/Buyflow/Storefront'
				headers = {
					'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					#cookie: __cfduid=d907b046dc2b4bfaf34b22bf4e36cb5b91596128690; phoneUpdate=default; check=true; _gcl_au=1.1.1913751777.1596128692; AMCVS_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1; _fbp=fb.1.1596128692148.1269726582; invoca_session=%7B%22ttl%22%3A%222020-08-29T17%3A04%3A52.244Z%22%2C%22session%22%3A%7B%7D%2C%22config%22%3A%7B%22campaignIdOverrideParam%22%3Anull%2C%22campaignIdOverrideValue%22%3Anull%2C%22requirementsNeeded%22%3Atrue%2C%22ce%22%3Atrue%7D%7D; s_cc=true; _ga=GA1.2.1633463053.1596128694; _gid=GA1.2.1346219299.1596128694; aam_uuid=51230999057439989541745199821450114878; IOTest=tenDollarPhone%3Dfalse%7C; connect.sid=s%3A1-IYvLoH-Ndfc0Y3n2_H-6BKM96p9Crg.NZcUUz1CftI14MBobgwkeoC98HCQBqNZRlSSl%2BV0Zrs; visid_incap_1012317=p6y4JcUkQQK+NBH+zgFmb879Il8AAAAAQUIPAAAAAABLrZn+0w6CYxLjU5mkbnVd; nlbi_1012317=EVA4f0B4gCzXq7XDZZ1JwgAAAAD+vG3npPJIB2LcL3d5J3ex; optimizelyEndUserId=oeu1596128719725r0.06892938416817374; _ga=GA1.3.1633463053.1596128694; _gid=GA1.3.1346219299.1596128694; SnapABugHistory=1#; aam_uuid=51230999057439989541745199821450114878; s_tbe_shop_order=1596129657100; AWSELB=01A95B1D141ABCE2F760790708E7A8CA24904814EC85EC39AA8737EAB7E35B87BAA3575BEBC4AE5481A6A96029DFEDF5416411D67DFB33E6204901A80D2C7F3CCA131A42AB; AWSELBCORS=01A95B1D141ABCE2F760790708E7A8CA24904814EC85EC39AA8737EAB7E35B87BAA3575BEBC4AE5481A6A96029DFEDF5416411D67DFB33E6204901A80D2C7F3CCA131A42AB; incap_ses_702_1012317=kACFUfc5dWrtHU4cdAG+CQEvI18AAAAAHp4lwgE+eO/te5cvbPj8QQ==; SnapABugRef=https%3A%2F%2Forder.optimum.com%2FBuyflow%2FStorefront%20; s_dfa=cablevis-uow-com; s_vnc365=1627677316063%26vn%3D3; s_ivc=true; AMCV_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1075005958%7CMCIDTS%7C18474%7CMCMID%7C51207873653272410511743008777202681743%7CMCAAMLH-1596746116%7C7%7CMCAAMB-1596746116%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1596148517s%7CNONE%7CvVersion%7C4.4.1; bounceClientVisit3324v=N4IgNgDiBcIBYBcEQM4FIDMBBNAmAYnvgPYBOAJgKakB0xECAlgLYCuzNAxsc0QEKsAngDMwxAO5EAygjKVhpYgDsEIADQhSMECAC+QA; s_sq=%5B%5BB%5D%5D; _uetsid=132f762cdc481d782c6006788b2bcaff; _uetvid=30d100605755205f246437df491f5f01; mp_95c15e221f6fe325df9f5b74d815bd35_mixpanel=%7B%22distinct_id%22%3A%20%22173a0af757335e-002d78435f8bbb-31627404-13c680-173a0af75745de%22%2C%22%24device_id%22%3A%20%22173a0af757335e-002d78435f8bbb-31627404-13c680-173a0af75745de%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.optimum.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22www.optimum.com%22%2C%22Referral%20Source%22%3A%20%22SDLCOM%22%2C%22Page%22%3A%20%22%2FBuyflow%2FStorefront%22%2C%22House%20Status%22%3A%20%22SUB%22%2C%22Current%20Customer%22%3A%20false%7D; SnapABugUserAlias=%23; SnapABugVisit=18#1596128721; mbox=PC#12ceebd257f94809a473eb10c070d230.35_0#1659386424|session#ddc95bd83a334e08947b0245ef7a0988#1596143175; _gat_UA-87150803-1=1; s_nr30=1596141625959-Repeat; s_tslv=1596141625960; opt_ev1=%5D%2C%22opt%253Aen%253Aresi%253Abuyflow%253Astorefront%22%5D%221596141625986%22%5B%2C; opt_ppn=opt%3Aen%3Aresi%3Abuyflow%3Astorefront; s_tbe_pros_order=1596141626298
					'sec-fetch-dest': 'document',
					'sec-fetch-mode': 'navigate',
					'sec-fetch-site': 'none',
					'sec-fetch-user': '?1',
					'upgrade-insecure-requests': '1',
					'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
				}

				r = s.get(url=url,headers=headers)
				print('got storefront')
				'''
				url = 'https://order.optimum.com/api/localize'

				headers = {
					'Accept': 'application/json, text/plain, */*',
					'Accept-Encoding': 'gzip, deflate, br',
					'Accept-Language': 'en-US,en;q=0.9',
					#'content-length': '238',
					'Content-Type': 'application/json;charset=UTF-8',
					#'Cookie': r"cookie: __cfduid=d907b046dc2b4bfaf34b22bf4e36cb5b91596128690; phoneUpdate=default; check=true; _gcl_au=1.1.1913751777.1596128692; AMCVS_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1; _fbp=fb.1.1596128692148.1269726582; invoca_session=%7B%22ttl%22%3A%222020-08-29T17%3A04%3A52.244Z%22%2C%22session%22%3A%7B%7D%2C%22config%22%3A%7B%22campaignIdOverrideParam%22%3Anull%2C%22campaignIdOverrideValue%22%3Anull%2C%22requirementsNeeded%22%3Atrue%2C%22ce%22%3Atrue%7D%7D; s_cc=true; _ga=GA1.2.1633463053.1596128694; _gid=GA1.2.1346219299.1596128694; aam_uuid=51230999057439989541745199821450114878; IOTest=tenDollarPhone%3Dfalse%7C; connect.sid=s%3A1-IYvLoH-Ndfc0Y3n2_H-6BKM96p9Crg.NZcUUz1CftI14MBobgwkeoC98HCQBqNZRlSSl%2BV0Zrs; visid_incap_1012317=p6y4JcUkQQK+NBH+zgFmb879Il8AAAAAQUIPAAAAAABLrZn+0w6CYxLjU5mkbnVd; nlbi_1012317=EVA4f0B4gCzXq7XDZZ1JwgAAAAD+vG3npPJIB2LcL3d5J3ex; optimizelyEndUserId=oeu1596128719725r0.06892938416817374; _ga=GA1.3.1633463053.1596128694; _gid=GA1.3.1346219299.1596128694; SnapABugHistory=1#; aam_uuid=51230999057439989541745199821450114878; s_tbe_shop_order=1596129657100; AWSELB=01A95B1D141ABCE2F760790708E7A8CA24904814EC85EC39AA8737EAB7E35B87BAA3575BEBC4AE5481A6A96029DFEDF5416411D67DFB33E6204901A80D2C7F3CCA131A42AB; AWSELBCORS=01A95B1D141ABCE2F760790708E7A8CA24904814EC85EC39AA8737EAB7E35B87BAA3575BEBC4AE5481A6A96029DFEDF5416411D67DFB33E6204901A80D2C7F3CCA131A42AB; incap_ses_702_1012317=kACFUfc5dWrtHU4cdAG+CQEvI18AAAAAHp4lwgE+eO/te5cvbPj8QQ==; SnapABugRef=https%3A%2F%2Forder.optimum.com%2FBuyflow%2FStorefront%20; s_dfa=cablevis-uow-com; s_vnc365=1627677316063%26vn%3D3; s_ivc=true; AMCV_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1075005958%7CMCIDTS%7C18474%7CMCMID%7C51207873653272410511743008777202681743%7CMCAAMLH-1596746116%7C7%7CMCAAMB-1596746116%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1596148517s%7CNONE%7CvVersion%7C4.4.1; bounceClientVisit3324v=N4IgNgDiBcIBYBcEQM4FIDMBBNAmAYnvgPYBOAJgKakB0xECAlgLYCuzNAxsc0QEKsAngDMwxAO5EAygjKVhpYgDsEIADQhSMECAC+QA; mp_95c15e221f6fe325df9f5b74d815bd35_mixpanel=%7B%22distinct_id%22%3A%20%22173a0af757335e-002d78435f8bbb-31627404-13c680-173a0af75745de%22%2C%22%24device_id%22%3A%20%22173a0af757335e-002d78435f8bbb-31627404-13c680-173a0af75745de%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.optimum.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22www.optimum.com%22%2C%22Referral%20Source%22%3A%20%22SDLCOM%22%2C%22Page%22%3A%20%22%2FBuyflow%2FStorefront%22%2C%22House%20Status%22%3A%20%22SUB%22%2C%22Current%20Customer%22%3A%20false%7D; mbox=PC#12ceebd257f94809a473eb10c070d230.35_0#1659386219|session#ddc95bd83a334e08947b0245ef7a0988#1596143175; SnapABugUserAlias=%23; SnapABugVisit=14#1596128721; _gat_UA-87150803-1=1; s_nr30=1596141419842-Repeat; s_tslv=1596141419843; opt_ev1=%5D%2C%22opt%253Aen%253Aresi%253Abuyflow%253Astorefront%22%5D%221596141419847%22%5B%2C; opt_ppn=opt%3Aen%3Aresi%3Abuyflow%3Astorefront; s_tbe_pros_order=1596141420046; _uetsid=132f762cdc481d782c6006788b2bcaff; _uetvid=30d100605755205f246437df491f5f01; _gat_gtag_UA_43239146_2=1; s_sq=cablevis-uow-com%3D%2526c.%2526a.%2526activitymap.%2526page%253Dopt%25253Aen%25253Aresi%25253Abuyflow%25253Astorefront%2526link%253DContinue%2526region%253Dbody%2526pageIDType%253D1%2526.activitymap%2526.a%2526.c%2526pid%253Dopt%25253Aen%25253Aresi%25253Abuyflow%25253Astorefront%2526pidt%253D1%2526oid%253DContinue%2526oidt%253D3%2526ot%253DSUBMIT",
					#'Cookie':  'cookie: connect.sid=' + s.cookies.get('connect.sid'),
					'Origin': 'https://order.optimum.com',
					'referer': 'https://order.optimum.com/Buyflow/Storefront',
					'sec-fetch-dest': 'empty',
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					#'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
				}

				data = {
					"enteredAddress": {
						"streetAddress":address.line1.upper(),
						"apartment":"",
						"zipCode":address.zipcode,
						"city":address.city,
						"state":address.state,
						"customerInteractionId":"51207873653272410511743008777202681743",
					},
					#"adobeVisitorId":"",
					#'experienceCloudVisitorId': "51207873653272410511743008777202681743",
					#'recaptchaResponse': "03AGdBq269FIqRbrANGMTejGdGGynnVgeDFMK0-TuEQxtbsheRhbJDAfbtbwItz4D64KhluIUpXsd9x9lRMXKbQu1bCEdN0AnWdhfDxanufAd16xw0ZqzlrC3BrPQAyxT7PFTcJ5YYplw4rYkRRyJMLOK_BKav6MZNPZsWQHaMtSAWP9IfN5X7q3zgDzbp_E6fTM2YXkmvCt7QhOBaqU7QwLmn0XOWinYCJa5fPDlJlPQ5JJSwc-5QDQIXoh0HPq5QrlnLK49U7JKjgJKDWZlT0aLx2kJ877oF2Ng281y71BPE1kKrSQy0V24j_bojXL9Kd5owubjfl4UnHSWHapOVeIQl3chGcy4AdvraxYNkQ1tvgEfPY37x_-PBRnn7_B_qvhwyZe8jnw7_UQ62Oxds7tA6I6pMDGIcng",
				}


				r = s.post(url=url, json=data, headers=headers)
				print(r.status_code)
				print(r.json())

				r = s.get(url=url, headers=headers)
				print(r.status_code)
				print(r.json())

				r = s.post(url=url, json=data, headers=headers)
				print(r.status_code)
				print(r.json())

				url = 'https://order.optimum.com/api/bundles'
				
				headers = {
					'accept': 'application/json, text/plain, */*',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					'referer': 'https://order.optimum.com/Buyflow/Products',
					'sec-fetch-dest': 'empty',
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					'user-agent': user_agent,#'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
				}

				r = s.get(url=url,headers=headers)

				response = r.json()
				if debug == True:
					pp.pprint(response)
				return

			# THIS ONE IS FULL CORRECT
			# Goes through whole buyflow process (to also get speeds)

			# 1)
			#for i in range(2):
			url = 'https://www.optimum.com/'
			headers = {
				'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
				#'cache-control': 'max-age=0',
				#'content-length': '203',
				'content-type': 'application/x-www-form-urlencoded',
				#'cookie': r"__cfduid=d8351b479d9ed403fbdef4fda1ed382581594668638; check=true; AMCVS_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1; s_cc=true; aam_uuid=51230999057439989541745199821450114878; _gcl_au=1.1.1331072260.1594668641; _ga=GA1.2.266684340.1594668642; _fbp=fb.1.1594668642447.1094612889; visid_incap_1012317=aPe5gQzAQAqUcwQg7d+S7Nq2DF8AAAAAQUIPAAAAAACFUBICk8YmUO0Sl2glfRnw; nlbi_1012317=PklSZv7VZzh2CeICZZ1JwgAAAADLBZ+1l3vsBeMMuPUveQup; optimizelyEndUserId=oeu1594668766971r0.20156832369467326; SnapABugHistory=1#; phoneUpdate=default; s_tbe_pros_order=1595463632759; invoca_session=%7B%22ttl%22%3A%222020-08-22T18%3A48%3A17.911Z%22%2C%22session%22%3A%7B%7D%2C%22config%22%3A%7B%22campaignIdOverrideParam%22%3Anull%2C%22campaignIdOverrideValue%22%3Anull%2C%22requirementsNeeded%22%3Atrue%2C%22ce%22%3Atrue%7D%7D; _gid=GA1.2.1053816064.1595818641; incap_ses_702_1012317=5Ay8cjV7CEsrIkQYdAG+CdCkIF8AAAAAQ5tOD59pwZTx+EeTqUGg7A==; mp_95c15e221f6fe325df9f5b74d815bd35_mixpanel=%7B%22distinct_id%22%3A%20%2217349aa5c5a203-0095857d2a1d39-31627404-1fa400-17349aa5c5b3e4%22%2C%22%24device_id%22%3A%20%2217349aa5c5a203-0095857d2a1d39-31627404-1fa400-17349aa5c5b3e4%22%2C%22House%20Status%22%3A%20%22NONSUB%22%2C%22Current%20Customer%22%3A%20false%2C%22Referral%20Source%22%3A%20%22SDLCOM%22%2C%22Page%22%3A%20%22%2FBuyflow%2FProducts%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.optimum.com%2Falticeone%22%2C%22%24initial_referring_domain%22%3A%20%22www.optimum.com%22%2C%22Offer%20Id%22%3A%20%22453174%22%2C%22Offer%20Name%22%3A%20%22Optimum%20300%22%2C%22Offer%20Lines%20of%20Business%20Count%22%3A%201%2C%22Fiber%20Offer%22%3A%20false%2C%22Offer%20Lines%20of%20Business%22%3A%20%22INTERNET%22%2C%22Offer%20TV%20Service%20Level%22%3A%20%22None%22%2C%22Offer%20Internet%20Service%20Level%22%3A%20300%2C%22Offer%20Phone%20Service%20Level%22%3A%20%22None%22%2C%22Offer%20Internet%20Speed%22%3A%20300%2C%22Offer%20Objective%22%3A%20%22ACQ%22%2C%22Offer%20Price%22%3A%2040%2C%22AAI%20Offer%22%3A%20false%2C%22Cart%20Monthly%20Cost%22%3A%2053.5%2C%22Cart%20Install%22%3A%200%2C%22Cart%20One%20Time%20Cost%22%3A%200%2C%22Cart%20Total%22%3A%2053.5%2C%22Modem%20Selection%22%3A%20%22Altice%20Modem%22%2C%22Promo%20Code%22%3A%20%22No%20Coupon%20Code%22%2C%22Amplify%20Selected%22%3A%20false%2C%22Apple%20TV%20Selected%22%3A%20false%2C%22Mobile%20Interest%22%3A%20false%2C%22Email%22%3A%20%22johnbell%40gmail.com%22%2C%22Order%20Automated%22%3A%20false%7D; SnapABugUserAlias=%23; SnapABugVisit=91#1594668770; s_tbe_shop_order=1595978161762; AMCV_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1075005958%7CMCIDTS%7C18473%7CMCMID%7C51207873653272410511743008777202681743%7CMCAAMLH-1596665255%7C7%7CMCAAMB-1596665255%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1596067655s%7CNONE%7CvVersion%7C4.4.1; mbox=PC#e7d6ccf937b64ee5b1148a802eb3503d.35_0#1659305257|session#ce10d9c758244a8089173b9378504c5e#1596062316; s_dfa=cablevis-uow-com; s_nr30=1596060463945-Repeat; s_tslv=1596060463950; s_vnc365=1627596463955%26vn%3D9; s_ivc=true; opt_ev1=%5D%2C%22optimum%253Aen%253Ahome%22%5D%221596060463967%22%5B%2C; opt_ppn=optimum%3Aen%3Ahome; _uetsid=66d3968e32c4af9a3c1ad38f8ec9c231; _uetvid=a48938b4e7e95bf061711e63417a4814; bounceClientVisit3324v=N4IgNgDiBcIBYBcEQM4FIDMBBNAmAYnvgO6kB0A9hAgJYC2ArnWQMYV1EgA0IATjCBABfIA; _gat_gtag_UA_110057334_22=1; _gat_gtag_UA_43239146_2=1; s_sq=cablevis-uow-com%3D%2526c.%2526a.%2526activitymap.%2526page%253Doptimum%25253Aen%25253Ahome%2526link%253DGet%252520offers%2526region%253Dedit-actions--3%2526pageIDType%253D1%2526.activitymap%2526.a%2526.c%2526pid%253Doptimum%25253Aen%25253Ahome%2526pidt%253D1%2526oid%253DGet%252520offers%2526oidt%253D3%2526ot%253DSUBMIT",
				'origin': 'https://www.optimum.com',
				'referer': 'https://www.optimum.com/',
				'sec-fetch-dest': 'document',
				'sec-fetch-mode': 'navigate',
				'sec-fetch-site': 'same-origin',
				'sec-fetch-user': '?1',
				'upgrade-insecure-requests': '1',
				'user-agent': user_agent,#'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
			}

			letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

			data = {
				'add1': address.line1,
				'add2': '', 
				'city': address.city,
				'state': address.state,
				'zip': address.zipcode,
				'op': 'Get offers',
				'form_build_id': f'form-{random.choice(letters)}UI{random.choice(letters)}FCj2_iTI{random.choice(letters)}1R{random.choice(letters)}zeV{random.choice(letters)}8Af{str(random.randint(0,9))}_{str(random.randint(0,9))}DJa{str(random.randint(0,9))}{str(random.randint(0,9))}Nh9-PgyCCT9Q',#.format(str(random.randint(0,9)),str(random.randint(0,9)),str(random.randint(0,9))),
				'form_id': 'webform_submission_find_offers_block_content_10_add_form',
			}

			r = s.post(url=url, data=data, headers=headers,timeout=30)


			soup = BeautifulSoup(r.text, "html.parser")
			if debug == True:
				print('TITLE1')
				print(r.status_code)
				pp.pprint(r.headers)
				print(soup.prettify())
				pass

			title1 = soup.title

			'''
			if title1 != None:
				break
			else:
				time.sleep(1)
				'''

			'''
			The below is used in the actual BAT, but it doesn't always return a consistent result with ^ (and ^ is consistent with when we test the BAT manually)
			url = f"https://order.optimum.com/Buyflow/Storefront?add1={address.line1.replace(' ','+')}&add2=&zip={address.zipcode}&token=45d4a416b57a063663301787d7343f579488460dd72769d3228c5bbad99d41d5"
			headers = {
				'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
				'cache-control': 'max-age=0',
				#cookie: __cfduid=d8351b479d9ed403fbdef4fda1ed382581594668638; check=true; AMCVS_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1; AMCV_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1075005958%7CMCIDTS%7C18457%7CMCMID%7C51207873653272410511743008777202681743%7CMCAAMLH-1595273439%7C7%7CMCAAMB-1595273439%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1594675839s%7CNONE%7CvVersion%7C4.4.1; mbox=session#e7d6ccf937b64ee5b1148a802eb3503d#1594670500|PC#e7d6ccf937b64ee5b1148a802eb3503d.35_0#1657913441; s_dfa=cablevis-uow-com; s_nr30=1594668640705-New; s_tslv=1594668640707; s_vnc365=1626204640708%26vn%3D1; s_ivc=true; opt_ev1=%5D%2C%22optimum%253Aen%253Aaltice%2520one%22%5D%221594668640710%22%5B%2C; opt_ppn=optimum%3Aen%3Aaltice%20one; s_tbe_pros_shop=1594668640729; s_cc=true; aam_uuid=51230999057439989541745199821450114878; _gcl_au=1.1.1331072260.1594668641; bounceClientVisit3324v=N4IgNgDiBcIBYBcEQM4FIDMBBNAmAYnvgO6kB0A9hAgJYC2ArnWQMYV1ECGYtLAphQB2fEABoQAJxghSxMgHMKFeWD6t2IAL5A; _uetsid=a525f1c0-c671-8efe-31c3-7df1c45b4e83; _uetvid=a48938b4-e7e9-5bf0-6171-1e63417a4814; _ga=GA1.2.266684340.1594668642; _gid=GA1.2.1235574776.1594668642; _fbp=fb.1.1594668642447.1094612889; s_sq=%5B%5BB%5D%5D
				'referer': 'https://www.optimum.com/alticeone',
				'sec-fetch-dest': 'document',
				'sec-fetch-mode': 'navigate',
				'sec-fetch-site': 'same-site',
				'sec-fetch-user': '?1',
				'upgrade-insecure-requests': '1',
				'user-agent': user_agent,
			}
			r = s.get(url=url, headers=headers, proxies=proxies)


			soup = BeautifulSoup(r.text, "html.parser")
			if debug == True:
				print('TITLE2')
				print(r.status_code)
				print(soup.prettify())
				pass

			title2 = soup.title
			'''
			if ('Optimum - Special Offers' in title1 or 'Optimum - Store Front' in title1):# and ('Optimum - Special Offers' in title2 or 'Optimum - Store Front' in title2):

				# 3) (skipped 2, seems like we don't need it...)
				url = 'https://order.optimum.com/api/bundles'
				
				headers = {
					'accept': 'application/json, text/plain, */*',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					'referer': 'https://order.optimum.com/Buyflow/Products',
					'sec-fetch-dest': 'empty',
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					'user-agent': user_agent,#'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
				}

				r = s.get(url=url,headers=headers)

				response = r.json()
				if debug == True:
					pp.pprint(response)

				# Check lines of business to confirm it has internet
				found_internet = False
				for line_of_b in response.get('availableLinesOfBusiness'):
					if line_of_b.get('name') == 'Internet':
						found_internet = True
				if found_internet == False:
					return CoverageResult(is_covered=32)

				# Get download speed and also confirm that the internet line of business is in a response
				max_downspeed = -1
				found_internet = False

				for offer in response.get('bundleOffers'):
					if 'H' in offer.get('linesOfBusiness'):
						found_internet = True
						if offer.get('internetSpeed') > max_downspeed:
							max_downspeed = offer.get('internetSpeed')

				if max_downspeed == -1:
					return RESPONSES['altice']['NO_SPEED']
				if found_internet == -1:
					return RESPONSES['altice']['NO_INTERNET']

				return CoverageResult(is_covered=COVERED_GENERAL,max_downspeed=max_downspeed)

			elif 'Optimum - No Service Available' in title1:
				return CoverageResult(is_covered=NOT_COVERED)
			elif 'Optimum - Select Address' in title1: #and 'Optimum - Select Address' in title2:

				no_matching_suggestion = False

				url = 'https://order.optimum.com/api/addressSelection'
				headers = {
					'accept': 'application/json, text/plain, */*',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					'referer': 'https://order.optimum.com/Buyflow/AddressSelection',
					'sec-fetch-dest': 'empty',
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					'user-agent': user_agent,
				}

				r = s.get(url=url,headers=headers)

				response = r.json()

				if debug == True:
					pp.pprint(response)

				new_address_index = -1
				new_line1 = None
				for suggestion in response.get('suggestions'):
					if 'Keep what I entered' in suggestion.get('topLine'):
						continue
					if address.line1 in suggestion.get('topLine').upper() and address.zipcode in suggestion.get('bottomLine').upper():
						new_address_index = suggestion.get('index')
						new_line1 = suggestion.get('topLine').upper()
						break
				if new_line1 != None:
					apt = new_line1.replace(address.line1 + ' ',"")
				else:
					apt = 'keep what i entered'
					new_address_index = -1
					no_matching_suggestion = True

				
				# For the below, for some reason the speed doesn't show so it's unclear whether the request works.
				if debug == True:
					print(f'NEW ADDRESS INDEX: {new_address_index}')
					print(f'APT:[{apt}]')

				# Redo request with address selection
				url = 'https://order.optimum.com/api/addressSelection'
				headers = {
					'accept': 'application/json, text/plain, */*',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					#'content-length: 27
					'content-type': 'application/json;charset=UTF-8',
					#'cookie: __cfduid=d8351b479d9ed403fbdef4fda1ed382581594668638; check=true; AMCVS_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1; s_cc=true; aam_uuid=51230999057439989541745199821450114878; _gcl_au=1.1.1331072260.1594668641; _ga=GA1.2.266684340.1594668642; _fbp=fb.1.1594668642447.1094612889; IOTest=tenDollarPhone%3Dfalse%7C; visid_incap_1012317=aPe5gQzAQAqUcwQg7d+S7Nq2DF8AAAAAQUIPAAAAAACFUBICk8YmUO0Sl2glfRnw; nlbi_1012317=PklSZv7VZzh2CeICZZ1JwgAAAADLBZ+1l3vsBeMMuPUveQup; optimizelyEndUserId=oeu1594668766971r0.20156832369467326; SnapABugHistory=1#; _ga=GA1.3.266684340.1594668642; aam_uuid=51230999057439989541745199821450114878; phoneUpdate=default; s_tbe_pros_order=1595463632759; invoca_session=%7B%22ttl%22%3A%222020-08-22T18%3A48%3A17.911Z%22%2C%22session%22%3A%7B%7D%2C%22config%22%3A%7B%22campaignIdOverrideParam%22%3Anull%2C%22campaignIdOverrideValue%22%3Anull%2C%22requirementsNeeded%22%3Atrue%2C%22ce%22%3Atrue%7D%7D; _gid=GA1.2.1053816064.1595818641; connect.sid=s%3Ax7PFS2GkBEBW7y-r1YiXV_YbRNao5SWX.%2FDHG7o1OldQEEvzC4C%2BaCXsk5vNNUuADq0V6Jwcfy7k; _gid=GA1.3.1053816064.1595818641; SnapABugRef=https%3A%2F%2Forder.optimum.com%2FBuyflow%2FNoService%20https%3A%2F%2Fwww.optimum.com%2F; AMCV_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1075005958%7CMCIDTS%7C18471%7CMCMID%7C51207873653272410511743008777202681743%7CMCAAMLH-1596576255%7C7%7CMCAAMB-1596576255%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1595978655s%7CNONE%7CvVersion%7C4.4.1; s_dfa=cablevis-uow-com; s_vnc365=1627510837278%26vn%3D8; s_ivc=true; bounceClientVisit3324v=N4IgNgDiBcIBYBcEQM4FIDMBBNAmAYnvgO6kB0A9hAgJYC2ArnWQMYV1ECGYtLAphQB2fEABoQAJxghSxMgHMKFeWD6t2IAL5A; AWSELB=01A95B1D141ABCE2F760790708E7A8CA24904814EC039AFA2554C2A7C55E8678827C0DC5B8ED9F2DC07EEC6FFAB4F4066E28D5B80E38D10111C4300F59FF3C4D637B4C5B0A; AWSELBCORS=01A95B1D141ABCE2F760790708E7A8CA24904814EC039AFA2554C2A7C55E8678827C0DC5B8ED9F2DC07EEC6FFAB4F4066E28D5B80E38D10111C4300F59FF3C4D637B4C5B0A; incap_ses_702_1012317=5Ay8cjV7CEsrIkQYdAG+CdCkIF8AAAAAQ5tOD59pwZTx+EeTqUGg7A==; s_tbe_shop_order=1595975077676; mp_95c15e221f6fe325df9f5b74d815bd35_mixpanel=%7B%22distinct_id%22%3A%20%2217349aa5c5a203-0095857d2a1d39-31627404-1fa400-17349aa5c5b3e4%22%2C%22%24device_id%22%3A%20%2217349aa5c5a203-0095857d2a1d39-31627404-1fa400-17349aa5c5b3e4%22%2C%22House%20Status%22%3A%20%22UNKNOWN%22%2C%22Current%20Customer%22%3A%20false%2C%22Referral%20Source%22%3A%20%22SDLCOM%22%2C%22Page%22%3A%20%22%2FBuyflow%2FAddressSelection%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.optimum.com%2Falticeone%22%2C%22%24initial_referring_domain%22%3A%20%22www.optimum.com%22%2C%22Offer%20Id%22%3A%20%22453174%22%2C%22Offer%20Name%22%3A%20%22Optimum%20300%22%2C%22Offer%20Lines%20of%20Business%20Count%22%3A%201%2C%22Fiber%20Offer%22%3A%20false%2C%22Offer%20Lines%20of%20Business%22%3A%20%22INTERNET%22%2C%22Offer%20TV%20Service%20Level%22%3A%20%22None%22%2C%22Offer%20Internet%20Service%20Level%22%3A%20300%2C%22Offer%20Phone%20Service%20Level%22%3A%20%22None%22%2C%22Offer%20Internet%20Speed%22%3A%20300%2C%22Offer%20Objective%22%3A%20%22ACQ%22%2C%22Offer%20Price%22%3A%2040%2C%22AAI%20Offer%22%3A%20false%2C%22Cart%20Monthly%20Cost%22%3A%2053.5%2C%22Cart%20Install%22%3A%200%2C%22Cart%20One%20Time%20Cost%22%3A%200%2C%22Cart%20Total%22%3A%2053.5%2C%22Modem%20Selection%22%3A%20%22Altice%20Modem%22%2C%22Promo%20Code%22%3A%20%22No%20Coupon%20Code%22%2C%22Amplify%20Selected%22%3A%20false%2C%22Apple%20TV%20Selected%22%3A%20false%2C%22Mobile%20Interest%22%3A%20false%2C%22Email%22%3A%20%22johnbell%40gmail.com%22%2C%22Order%20Automated%22%3A%20false%7D; SnapABugUserAlias=%23; SnapABugVisit=61#1594668770; mbox=PC#e7d6ccf937b64ee5b1148a802eb3503d.35_0#1659219923|session#a11aff738a504ef2867ab04d02fcdde0#1595976695; s_nr30=1595975122983-Repeat; s_tslv=1595975122984; opt_ev1=%5D%2C%22opt%253Aen%253Aresi%253Abuyflow%253Aaddressselection%22%5D%221595975122992%22%5B%2C; opt_ppn=opt%3Aen%3Aresi%3Abuyflow%3Aaddressselection; _uetsid=66d3968e32c4af9a3c1ad38f8ec9c231; _uetvid=a48938b4e7e95bf061711e63417a4814; s_sq=cablevis-uow-com%3D%2526c.%2526a.%2526activitymap.%2526page%253Dopt%25253Aen%25253Aresi%25253Abuyflow%25253Aaddressselection%2526link%253DContinue%2526region%253Dbody%2526pageIDType%253D1%2526.activitymap%2526.a%2526.c%2526pid%253Dopt%25253Aen%25253Aresi%25253Abuyflow%25253Aaddressselection%2526pidt%253D1%2526oid%253DContinue%2526oidt%253D3%2526ot%253DSUBMIT
					'origin': 'https://order.optimum.com',
					'referer': 'https://order.optimum.com/Buyflow/AddressSelection',
					'sec-fetch-dest': 'empty',
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					'user-agent': user_agent,
				}
				data = {
					'selectedAddressIndex': new_address_index,
				}

				r = s.post(url=url,headers=headers,json=data)
				response = r.json()

				if debug == True:
					print('POST ADDRESS SELECTION')
					print(soup.prettify())

				# Request the products page
				'''
				url = 'https://order.optimum.com/Buyflow/Products'
				headers = {
					'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					#cookie: __cfduid=d8351b479d9ed403fbdef4fda1ed382581594668638; check=true; AMCVS_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1; s_cc=true; aam_uuid=51230999057439989541745199821450114878; _gcl_au=1.1.1331072260.1594668641; _ga=GA1.2.266684340.1594668642; _fbp=fb.1.1594668642447.1094612889; IOTest=tenDollarPhone%3Dfalse%7C; visid_incap_1012317=aPe5gQzAQAqUcwQg7d+S7Nq2DF8AAAAAQUIPAAAAAACFUBICk8YmUO0Sl2glfRnw; nlbi_1012317=PklSZv7VZzh2CeICZZ1JwgAAAADLBZ+1l3vsBeMMuPUveQup; optimizelyEndUserId=oeu1594668766971r0.20156832369467326; SnapABugHistory=1#; _ga=GA1.3.266684340.1594668642; aam_uuid=51230999057439989541745199821450114878; phoneUpdate=default; s_tbe_pros_order=1595463632759; invoca_session=%7B%22ttl%22%3A%222020-08-22T18%3A48%3A17.911Z%22%2C%22session%22%3A%7B%7D%2C%22config%22%3A%7B%22campaignIdOverrideParam%22%3Anull%2C%22campaignIdOverrideValue%22%3Anull%2C%22requirementsNeeded%22%3Atrue%2C%22ce%22%3Atrue%7D%7D; _gid=GA1.2.1053816064.1595818641; connect.sid=s%3Ax7PFS2GkBEBW7y-r1YiXV_YbRNao5SWX.%2FDHG7o1OldQEEvzC4C%2BaCXsk5vNNUuADq0V6Jwcfy7k; _gid=GA1.3.1053816064.1595818641; SnapABugRef=https%3A%2F%2Forder.optimum.com%2FBuyflow%2FNoService%20https%3A%2F%2Fwww.optimum.com%2F; AMCV_BBEC02BE53309F2E0A490D4C%40AdobeOrg=1075005958%7CMCIDTS%7C18471%7CMCMID%7C51207873653272410511743008777202681743%7CMCAAMLH-1596576255%7C7%7CMCAAMB-1596576255%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1595978655s%7CNONE%7CvVersion%7C4.4.1; s_dfa=cablevis-uow-com; s_vnc365=1627510837278%26vn%3D8; s_ivc=true; incap_ses_702_1012317=5Ay8cjV7CEsrIkQYdAG+CdCkIF8AAAAAQ5tOD59pwZTx+EeTqUGg7A==; bounceClientVisit3324v=N4IgNgDiBcIBYBcEQM4FIDMBBNAmAYnvgO6kB0A9hAgJYC2ArnWQMYV1EgA0IATjCBABfIA; AWSELB=01A95B1D141ABCE2F760790708E7A8CA24904814EC039AFA2554C2A7C55E8678827C0DC5B8ED9F2DC07EEC6FFAB4F4066E28D5B80E38D10111C4300F59FF3C4D637B4C5B0A; AWSELBCORS=01A95B1D141ABCE2F760790708E7A8CA24904814EC039AFA2554C2A7C55E8678827C0DC5B8ED9F2DC07EEC6FFAB4F4066E28D5B80E38D10111C4300F59FF3C4D637B4C5B0A; s_tbe_shop_order=1595977086716; mp_95c15e221f6fe325df9f5b74d815bd35_mixpanel=%7B%22distinct_id%22%3A%20%2217349aa5c5a203-0095857d2a1d39-31627404-1fa400-17349aa5c5b3e4%22%2C%22%24device_id%22%3A%20%2217349aa5c5a203-0095857d2a1d39-31627404-1fa400-17349aa5c5b3e4%22%2C%22House%20Status%22%3A%20%22SUB%22%2C%22Current%20Customer%22%3A%20false%2C%22Referral%20Source%22%3A%20%22SDLCOM%22%2C%22Page%22%3A%20%22%2FBuyflow%2FAddressSelection%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.optimum.com%2Falticeone%22%2C%22%24initial_referring_domain%22%3A%20%22www.optimum.com%22%2C%22Offer%20Id%22%3A%20%22453174%22%2C%22Offer%20Name%22%3A%20%22Optimum%20300%22%2C%22Offer%20Lines%20of%20Business%20Count%22%3A%201%2C%22Fiber%20Offer%22%3A%20false%2C%22Offer%20Lines%20of%20Business%22%3A%20%22INTERNET%22%2C%22Offer%20TV%20Service%20Level%22%3A%20%22None%22%2C%22Offer%20Internet%20Service%20Level%22%3A%20300%2C%22Offer%20Phone%20Service%20Level%22%3A%20%22None%22%2C%22Offer%20Internet%20Speed%22%3A%20300%2C%22Offer%20Objective%22%3A%20%22ACQ%22%2C%22Offer%20Price%22%3A%2040%2C%22AAI%20Offer%22%3A%20false%2C%22Cart%20Monthly%20Cost%22%3A%2053.5%2C%22Cart%20Install%22%3A%200%2C%22Cart%20One%20Time%20Cost%22%3A%200%2C%22Cart%20Total%22%3A%2053.5%2C%22Modem%20Selection%22%3A%20%22Altice%20Modem%22%2C%22Promo%20Code%22%3A%20%22No%20Coupon%20Code%22%2C%22Amplify%20Selected%22%3A%20false%2C%22Apple%20TV%20Selected%22%3A%20false%2C%22Mobile%20Interest%22%3A%20false%2C%22Email%22%3A%20%22johnbell%40gmail.com%22%2C%22Order%20Automated%22%3A%20false%7D; SnapABugUserAlias=%23; SnapABugVisit=87#1594668770; mbox=PC#e7d6ccf937b64ee5b1148a802eb3503d.35_0#1659222024|session#e3aa66915d68408a81319e0db9801510#1595978568; s_nr30=1595977227402-Repeat; s_tslv=1595977227404; opt_ev1=%5D%2C%22opt%253Aen%253Aresi%253Abuyflow%253Aaddressselection%22%5D%221595977227409%22%5B%2C; opt_ppn=opt%3Aen%3Aresi%3Abuyflow%3Aaddressselection; _uetsid=66d3968e32c4af9a3c1ad38f8ec9c231; _uetvid=a48938b4e7e95bf061711e63417a4814; s_sq=cablevis-uow-com%3D%2526c.%2526a.%2526activitymap.%2526page%253Dopt%25253Aen%25253Aresi%25253Abuyflow%25253Aaddressselection%2526link%253DContinue%2526region%253Dbody%2526pageIDType%253D1%2526.activitymap%2526.a%2526.c%2526pid%253Dopt%25253Aen%25253Aresi%25253Abuyflow%25253Aaddressselection%2526pidt%253D1%2526oid%253DContinue%2526oidt%253D3%2526ot%253DSUBMIT
					'referer': 'https://order.optimum.com/Buyflow/AddressSelection',
					'sec-fetch-dest': 'document',
					'sec-fetch-mode': 'navigate',
					'sec-fetch-site': 'same-origin',
					'sec-fetch-user': '?1',
					'upgrade-insecure-requests': '1',
					'user-agent': user_agent,#Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36
				}

				r = s.get(url=url,headers=headers,proxies=proxies)
				soup = BeautifulSoup(r.text, "html.parser")
				if debug == True:
					print('PRODUCTS')
					print(soup.prettify())
					'''

				'''
				url = 'https://order.optimum.com/api/localize'
				headers = {
					'accept': 'application/json, text/plain, */*',
					'accept-encoding': 'gzip, deflate, br',
					'accept-language': 'en-US,en;q=0.9',
					'referer': 'https://order.optimum.com/Buyflow/Products',
					'sec-fetch-dest': 'empty',
					#'cookie': s.cookies.get('connect.sid'),
					'sec-fetch-mode': 'cors',
					'sec-fetch-site': 'same-origin',
					'user-agent': user_agent,#'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
				}

				r = s.get(url=url,headers=headers)
				if debug == True:
					print('LOCALIZE')
					pp.pprint(r.json())
				'''
				if response.get('redirectUrl') == 'Products':
					# Get speed info if exists
					url = 'https://order.optimum.com/api/bundles'
					
					headers = {
						'accept': 'application/json, text/plain, */*',
						'accept-encoding': 'gzip, deflate, br',
						'accept-language': 'en-US,en;q=0.9',
						'referer': 'https://order.optimum.com/Buyflow/Products',
						'sec-fetch-dest': 'empty',
						#'cookie': cookie,
						'sec-fetch-mode': 'cors',
						'sec-fetch-site': 'same-origin',
						'user-agent': user_agent,#'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
					}

					#pp.pprint(s.cookies)

					r = s.get(url=url,headers=headers)

					response = r.json()
					if debug == True:
						print('BUNDLES')
						print(r.status_code)
						pp.pprint(s.cookies)
						pp.pprint(response)


					# Check lines of business to confirm it has internet
					found_internet = False
					for line_of_b in response.get('availableLinesOfBusiness'):
						if line_of_b.get('name') == 'Internet':
							found_internet = True
					if found_internet == False:
						return CoverageResult(is_covered=33)

					# Get download speed and also confirm that the internet line of business is in a response
					max_downspeed = -1
					found_internet = False

					for offer in response.get('bundleOffers'):
						if 'H' in offer.get('linesOfBusiness'):
							found_internet = True
							if offer.get('internetSpeed') > max_downspeed:
								max_downspeed = offer.get('internetSpeed')

					if max_downspeed == -1:
						return RESPONSES['altice']['NO_SPEED']
					if found_internet == -1:
						return RESPONSES['altice']['NO_INTERNET']

					if no_matching_suggestion == False:
						return CoverageResult(is_covered=COVERED_GENERAL,max_downspeed=max_downspeed)
					else:
						return CoverageResult(is_covered=RESPONSES['altice']['COVERED_NO_MATCH'],max_downspeed=max_downspeed)
				else:
					return CoverageResult(is_covered=35)
			elif 'Optimum - Unsupported Browser' in title1:# and 'Optimum - Unsupported Browser' in title2:
				return CoverageResult(is_covered=RESPONSES['altice']['UNSUPPORTED_BROWSER'])
			else:
				return CoverageResult(is_covered=UNKNOWN)

		# ISP: Sonic
		# Auto: issue with this one (need to find way to get async id)
		elif isp == 'sonic':
			raise Exception(EXCEPTION_MESSAGE)
			url = 'https://www.sonic.com/sites/all/modules/contrib/sonic/sonic_availability/altavailability/api.php?do=prequal_poll'

			headers = {
				'Origin':'https://www.sonic.com',
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36',
				'content-type':'application/json; charset=UTF-8',
				'Accept':'*/*',
			}

			body = {
				"street_address": address.line1,
				"secondary":"",
				"zip_code": address.zipcode,
				"service_type":"residential",
				"sso_user":"",
				"eloqua_customer_id":"",
				"poll":'true',
				"async_id":"e88ae3aa-ea8a-4ab6-9182-f3bad3fa84e1",
			}

			r = requests.post(url=url, json=body, headers=headers)
			response = r.json()

			response = response.get('result').get('response')

			pp.pprint(response)
			if response.get('service_available') == 0:
				return CoverageResult(is_covered = False)
			else:
				try:
					products = response.get('products_available').get('fusion')
				except:
					return CoverageResult(is_covered = False)
				max_speed = -1
				for product in products:
					if int(product.get('access_downstream_speed')) > max_speed:
						max_speed = int(product.get('access_downstream_speed'))
				return CoverageResult(is_covered = True, speed=max_speed)

			pp.pprint(response)
			
		# ISP: Suddenlink (owned by Altice)
		elif isp == 'suddenlink':
			s = requests.session()
			raise Exception(EXCEPTION_MESSAGE)
			
			url = 'https://order.suddenlink.com/Buyflow/Storefront?add1=511+Wade+St&add2=&zip=71901&token=c43e953aee9945520f099ed71c792489a27aa99b3c386b8fc2225fb3f56f7583'
			headers = {
				'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
				'cache-control': 'max-age=0',
				'referer': 'https://www.suddenlink.com/',
				'sec-fetch-dest': 'document',
				'sec-fetch-mode': 'navigate',
				'sec-fetch-site': 'same-site',
				'sec-fetch-user': '?1',
				'upgrade-insecure-requests': '1',
				'user-agent': user_agent,
			}
			r = s.get(url=url,headers=headers)

			soup = BeautifulSoup(r.text, "html.parser")
			print(soup.prettify())
			exit()


		# ISP: TDS Telecom
		# Can only do by zip currently because we get authorization error when requesting info for
		# an address
		elif isp =='tds_telecom':
			raise Exception(EXCEPTION_MESSAGE)
			url = 'https://tdstelecom.com/bin/tds-common/readonly/address/verifyzip?zip=' + address.zipcode

			headers = {
				'Accept':'*/*',
				'X-Requested-With':'XMLHttpRequest',
				'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36',
				'Sec-Fetch-Mode':'cors',
				'Cache-Control': 'no-cache',
				'Postman-Token': '4cdf5eed-b328-4c67-913e-68c5f67a4d45',
				'Host': 'tdstelecom.com',
				'Accept-Encoding': 'gzip, deflate',
				'Connection': 'keep-alive',
			}

			body = {
				'zip': address.zipcode
			}

			r = requests.get(url=url, json=body, headers=headers)
			response = r.json()

			if response.get('is_serviceable') == False:
				return False
			elif response.get('is_serviceable') == True:
				return True
		
		# ISP: Verizon
		elif isp == 'verizon':

			# Fix the prefixes of the suggested address
			def fix_line1(old_line1):
				suggested_line_1_words = old_line1.split(' ')
				suggested_street_type = suggested_line_1_words[len(suggested_line_1_words)-1]
				if suggested_street_type in STREET_PREFIXES:
					new_street_type = STREET_PREFIXES[suggested_street_type]
					suggested_line_1_words[len(suggested_line_1_words)-1] = new_street_type
					new_suggested_address_line1 = ' '.join(suggested_line_1_words)

					if debug == True:
						print('NEW SUGGESTED ADDRESS LINE1: ' + new_suggested_address_line1)
					return new_suggested_address_line1
				else:
					return old_line1

			s = requests.Session()
			requests.packages.urllib3.disable_warnings() 


			# 0a. Get access token
			url = 'https://www.verizon.com/inhome/generatetoken'
			headers = {
				'User-Agent': user_agent,
				'Accept-Language' : 'en,en-US;q=0,5',
				'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,/;q=0.8"',
			}
			r = s.get(url=url, headers=headers, proxies=proxies, verify=False)

			response = r.json()
			token = response.get('access_token')
			
			if debug == True:
				pp.pprint(response)

			# 0b. Get visitor id cookie:
			headers = {
				'Host': 'www.verizon.com',
				'Connection': 'keep-alive',
				#'Gsm-Id': 'NES3%2B2Z7r8vPzjqPV67nIKPOJmLZB4%2F38B9Toh74a2JBlZck%2F03AJHwMj7u8UF1p%2FHH',
				'Pragma': 'no-cache',
				'Authorization': 'Bearer ' + token,
				'Content-Type': 'application/json',
				'Accept': 'application/json, text/plain, */*',
				'Cache-Control': 'no-store',
				'User-Agent': user_agent,
				'Sec-Fetch-Site': 'same-origin',
				'Sec-Fetch-Mode': 'cors',
				'Referer': 'https://www.verizon.com/inhome/qualification?lid=//global//residential',
				'Accept-Encoding': 'gzip, deflate, br',
				'Accept-Language': 'en-US,en;q=0.9',
			}

			r = s.get(url='https://www.verizon.com/inhome/generatevisitid', headers=headers, proxies=proxies, verify=False)

			response = r.json()
			if debug == True:
				print("VISITOR ID:")
				pp.pprint(r.json())
			visit_id = response.get('visit_id')

			# 1a. Check whether zip is covered
			url = 'https://api.verizon.com/atomapi/v1/addresslookup/addresses/zip?zipcityterm=' + address.zipcode

			headers = {
				'Origin':'https://www.verizon.com',
				'Authorization':'Bearer ' + token,
				'User-Agent': user_agent,
			}
			r = s.get(url=url, headers=headers, proxies=proxies, verify=False)

			result = r.json()

			if debug == True:
				print("GETTING ZIP")
				pp.pprint(result)

			if result.get('meta').get('code') == '200.1':
				found = False
				for zipcode in result.get('zips'):
					if zipcode.get('zip') == address.zipcode:
						found = True
						break
				
				if found == False:
					return {
						50: CoverageResult(is_covered = RESPONSES['verizon']['NOT_COVERED_ZIP']),
						10: CoverageResult(is_covered = RESPONSES['verizon']['NOT_COVERED_ZIP'])
					}
			else:
				raise Exception()

			# 1b. Getting addressId 

			# First, if our address has prefixes in it, we need to change those
			address.line1 = fix_line1(address.line1)
			if debug == True:
				print('NEW ADDRESS (FORMATTING) LINE1: {}'.format(address.line1))

			url = f'https://api.verizon.com/atomapi/v1/addresslookup/addresses/streetbyzip?zip={address.zipcode}&streetterm={address.line1}'

			# Make the request
			headers = {
				'Origin':'https://www.verizon.com',
				'Authorization':'Bearer ' + token,
				'User-Agent': user_agent,
			}

			if debug == True:
				print('getting address id...')

			r = s.get(url=url, headers=headers, proxies=proxies, verify=False)
			response = r.json()

			if debug == True:
				print(url)
				print("ADDRESS_ID")
				pp.pprint(response)

			address_id = '0'

			if response.get('meta').get('code') in ['200.1','200.01']:

				for address_json in response.get('addressesbau'):
					if address_json.get('street') is not None:
						suggested_address_line1 = fix_line1(address_json.get('street'))
						if debug == True:
							print('New address suggestion : ' + suggested_address_line1)
					# Often, zip doesn't exist and state is None, so we need to verify the accuracy fully by line1 (potentially trivky in cases where there can be streets with the same name in a zipcode, but this is how Verizon's UI works so not much we can do)
					if address_json.get('street') is not None and suggested_address_line1.upper() in address.line1 and (address_json.get('state') is None or address_json.get('state').upper() == address.state):   # and address_json.get('zip') == address.zipcode:
						address_id = address_json.get('addressID')

						# Shortcut of a sort: sometimes information is returned here that indicates Fios is available
						if True:
							if address_json.get('ivappData') is not None:
								if address_json.get('ivappData').get('maxdwnstrmspddisp') is not None and address_json.get('ivappData').get('maxdwnstrmspddisp') not in ['','0']:
									return {
										50: CoverageResult(is_covered = RESPONSES['verizon']['FIOS_EARLY_COVERED']),
										10: CoverageResult(is_covered = RESPONSES['verizon']['FIOS_EARLY_COVERED'])
									}
						break

			else:
				return {
					50: CoverageResult(is_covered = UNKNOWN),
					10: CoverageResult(is_covered = UNKNOWN)
				}

			if debug == True:
				print("ADDRESS_ID: " + address_id)

			# 1c. Check if building has apartments, and if so, get address-specific apt id
			if address_id != '0':
				url = 'https://api.verizon.com/atomapi/v1/addresslookup/addresses/units?baseAddressId=' + address_id

				headers = {
					'Authorization':'Bearer ' + token ,
					'User-Agent': user_agent,
				}

				if debug == True:
					print('Getting apt specific ID...')
				r = s.get(url=url, headers=headers, proxies=proxies, verify=False)
				response = r.json()

				if debug == True:
					print("APT-SPECIFIC ADDRESS_ID")
					pp.pprint(response)


				# Get an addr_id that is specific to an apt in the building (any addr_id works)
				if int(response.get('data').get('total')) != 0:
					address_id = response.get('data').get('unitDetails')[0].get('addressId')

				if debug == True:
					print("NEW APT-SPECIFIC: ADDRESS_ID: " + address_id)


			# 2. Use addressId to get coverage info
			if address_id != '0':
				url = 'https://api.verizon.com/atomapi/v1/addressqualification/address/qualification?addressID=' + address_id + '&state=' + address.state + '&zip=' + address.zipcode + '&isRememberMe=N&oneLQ=Y&city=' + address.city
			else:
				url = 'https://api.verizon.com/atomapi/v1/addressqualification/address/qualification?addressID=0&state=' + address.state + '&zip=' + address.zipcode + '&isRememberMe=N&addressLine1=' + address.fullAddressNoZip()
				url = url.replace(' ', '%20')
			headers = {
				'Authorization':'Bearer ' + token ,
				'Host': 'api.verizon.com',
				'Connection': 'keep-alive',
				'Gsm-Id':'', 
				'Pragma': 'no-cache',
				'Content-Type': 'application/json',
				'Accept': 'application/json, text/plain, */*',
				'Cache-Control': 'no-storev',
				'User-Agent': user_agent,
				'Origin': 'https://www.verizon.com',
				'Sec-Fetch-Site': 'same-site',
				'Sec-Fetch-Mode': 'cors',
				'Referer': 'https://www.verizon.com/inhome/qualification?change=Y',
				'Accept-Encoding': 'gzip, deflate, br',
				'Accept-Language': 'en-US,en;q=0.9',
			}

			# The last request specifically is the one that gets rate-limited, so we'll use special IPs specifically for these ones
			coverage_proxy = proxies_r

			attempt_0_coverages = dict()
			for attempt in range(2):

				for j in range(2):
					try:
						r = s.get(url=url, headers=headers, proxies=coverage_proxy,verify=False)
						response = r.json()
						if debug == True:
							print("COVERAGE INFO")
							print(url)
							pp.pprint(response)
						if str(response.get('meta').get('code')) not in ['200.01','200.1']:
							raise Exception()
						break
					except:
						pass

				coverage = None


				coverages = dict()

				new_address_id = None
				# In this case, they suggest an alternative address
				if str(response.get('meta').get('code')) in ['200.01','200.1'] and response.get('data').get('services') == None and response.get('data').get('addressNotFound') == False:
					for parsed_address in response.get('data').get('parsedAddress'):
						fix_parsed_address_line1 = fix_line1(parsed_address.get('street'))

						# We check for the address in the other, since verizon sometimes excludes street type (i.e. instead of '41 Umberland St', they have '41 umberland'
						if fix_parsed_address_line1 in address.line1 and address.zipcode in parsed_address.get('zipCode') and parsed_address.get('addressID') is not None and parsed_address.get('addressID') != '':
							new_address_id = str(int(float(parsed_address.get('addressID'))))
							break
					if new_address_id is None:
						return {
								50: CoverageResult(is_covered = RESPONSES['verizon']['NO_ADDRESS_MATCH']),
								10: CoverageResult(is_covered = RESPONSES['verizon']['NO_ADDRESS_MATCH'])
							}
					else:
						address_id = new_address_id
						url = 'https://api.verizon.com/atomapi/v1/addressqualification/address/qualification?addressID=' + address_id + '&state=' + address.state + '&zip=' + address.zipcode + '&isRememberMe=N&multiadr=Y'
						url = url.replace(' ', '%20')

						for j in range(2):
							try:
								r = s.get(url=url, headers=headers, proxies=coverage_proxy,verify=False)
								response = r.json()
								break
							except:
								pass

						if debug == True:
							print(f'NEW ADDRESS_ID: {new_address_id}')
							print("COVERAGE INFO AFTER REDO")
							print(url)
							pp.pprint(response)


				# The response is good
				if str(response.get('meta').get('code')) in ['200.01','200.1']:
					# Address isn't recognized
					if response.get('data').get('addressNotFound') == True:
						coverages[50] = CoverageResult(is_covered = NOT_RECOGNIZED)
						coverages[10] = CoverageResult(is_covered = NOT_RECOGNIZED)
						return coverages
					if response.get('data').get('services') == None:
						coverages[50] = CoverageResult(is_covered = RESPONSES['verizon']['NO_COVERAGE_INFO'])
						coverages[10] = CoverageResult(is_covered = RESPONSES['verizon']['NO_COVERAGE_INFO'])
						return coverages
					# Confirm address matches when address id is 0
					if address_id == '0':
						found = False
						for parsed_address in response.get('data').get('parsedAddress'):
							if address.line1 in parsed_address.get('addressString') and address.zipcode in parsed_address.get('addressString'):
								found = True
							else:
								# Also reformat street name for suggested adddress (for example they return 'AVE as 'AV')
								new_suggested_address_line1 = fix_line1(parsed_address.get('street'))
								#print('NEW SUGGESTED STREET ADDRESS: {}'.format(new_suggested_address_line1))
								if address.line1 in new_suggested_address_line1 and address.zipcode in parsed_address.get('addressString'):
									found = True
						if found == False:
							return {
								50: CoverageResult(is_covered = RESPONSES['verizon']['ADDRESS_DOES_NOT_MATCH']),
								10: CoverageResult(is_covered = RESPONSES['verizon']['ADDRESS_DOES_NOT_MATCH'])
							}

					# Get coverage for each service
					for service in response.get('data').get('services'):
						if service.get('servicename') == 'FiOSData':
							if service.get('qualified') == 'Y':
								coverages[50] = CoverageResult(is_covered = COVERED_GENERAL)
							elif service.get('qualified') == 'N':
								coverages[50] = CoverageResult(is_covered = NOT_COVERED)
							else:
								coverages[50] = CoverageResult(is_covered = 101)
						if service.get('servicename') == 'HSI':
							if service.get('qualified') == 'Y':
								coverages[10] = CoverageResult(is_covered = COVERED_GENERAL)
							elif service.get('qualified') == 'N':
								coverages[10] = CoverageResult(is_covered = NOT_COVERED)
							else:
								coverages[10] = CoverageResult(is_covered = 101)
								pp.pprint(service.get('qualified'))
								pp.pprint(response)

				else:
					return {
						50: CoverageResult(is_covered = UNKNOWN),
						10: CoverageResult(is_covered = UNKNOWN)
					}

				if attempt == 0:
					attempt_0_coverages = coverages
				elif attempt == 1:
					if attempt_0_coverages[10].is_covered == coverages[10].is_covered and attempt_0_coverages[50].is_covered == coverages[50].is_covered:
						return coverages
					else:
						raise Exception('Results do not match')
			
			return coverages

			'''
			# The below code is incomplete but can be used for speed info

			# Add coverage details for each result that is covered
			if coverages[50].is_covered == COVERED_GENERAL:
				url = 'https://api.verizon.com/atomapi/v1/qualifiedproducts/accordion/products/plans'

				body = {
					"uid": visit_id,
					"idType":"visit",
					"contract":"MTM",
					"isPromoInclude":False,
					"serviceType":"Data",
					"intents":[]
				}

				headers = {

					'Host': 'api.verizon.com',
					'Connection': 'keep-alive',
					'Content-Length': '126',
					'Pragma': 'no-cache',
					'Authorization': 'Bearer ' + token , #'Bearer 1dt0ddjM7v5rlHDJIJX3RGlzIxlJ',# + 
					'Content-Type': 'application/json',
					'Accept': 'application/json, text/plain, */*',
					'Cache-Control': 'no-store',
					'User-Agent': user_agent,
					'Origin': 'https://www.verizon.com',
					'Sec-Fetch-Site': 'same-site',
					'Sec-Fetch-Mode': 'cors',
					'Referer': 'https://www.verizon.com/inhome/buildproducts',
					'Accept-Encoding': 'gzip, deflate, br',
					'Accept-Language': 'en-US,en;q=0.9',
				}

				r = s.post(url=url, json=body, headers=headers, proxies=proxies, verify=False)

				result = r.json()

				if debug == True:
					pp.pprint(result)

				products = result.get('data').get('products')

				max_speed = 0
				try:
					for product in products:
						speed = product.get('downSpeed')
						
						# Remove 'M' from end and convert to int
						speed = int(speed[:len(speed)-1])

						if speed > max_speed:
							max_speed = speed

					coverages[50].down_speed = speed
				except:
					return {
						50: CoverageResult(is_covered = RESPONSES['verizon']['GET_SPEED_ERROR']),
						10: CoverageResult(is_covered = RESPONSES['verizon']['GET_SPEED_ERROR'])
					}

			# This isn't working at the moment
			if coverages[10].is_covered != COVERED_GENERAL:

				url = 'https://www.verizon.com/foryourhome/ordering/checkavailabilitylq.aspx?src=frmAtom'

				headers = {
					'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
					'Accept-Encoding': 'gzip, deflate, br',
					'Accept-Language': 'en-US,en;q=0.9',
					'Connection': 'keep-alive',
					'Authorization': 'Bearer ' + token ,
					#'Cookie: s_sq=%5B%5BB%5D%5D; qualification=seg%3D7087294%2Cseg%3D7195725; aam_uuid=88749760752721138490904160119360806587; AkaSTrackingID=8f35f2614ed40577a51911dcd0f85858; AMCVS_777B575E55828EBB7F000101%40AdobeOrg=1; s_ecid=MCMID%7C88733049013919627130901362749153428059; check=true; _cls_v=0fd86e33-1845-435b-898b-380be562bb56; _cls_s=3c1c58f9-4d46-45e7-8bdd-c786ce4d0044:0; kampyle_userid=686b-3f28-96ce-e0f9-50a0-57d8-1ac3-cc65; _ga=GA1.2.29506293.1580941508; cd_user_id=1701774ff051ca-07f97546e34131-39647b09-13c680-1701774ff06742; s_cc=true; visitor_id=NESzs24CutmHio29Oghe6%2BTeJjSI0tCl1zA%2Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; chat_gsid=NESzs24CutmHio29Oghe6%252BTeJjSI0tCl1zA%252Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; ASP.NET_SessionId=z2wvu00yypc1e3logjhspo5w; VZ_ATLAS_SITE_PERS=BusinessUnit=residential; NESzs24CutmHio29Oghe6%2BTeJjSI0tCl1zA%2Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; UST=et=2020-2-14&c=1; _gid=GA1.2.423891174.1581699133; kampyleUserSession=1581699232504; kampyleUserSessionsCount=4; TC_CHAT_IN_PROGRESS=; XSRF-TOKEN=4E45533936316A4A736868715176537739414E3075552F4269544167717373527762777337754D4A5575617A706D786E4737733766526238516E662F56624A72746642; EOrdering=isatom=N&DTP=D&TPXPSINFO=&PSF=&DOON=&RVD=&RVDT=&VF=&_e_=NESDdu2T7V54NiKPv2wfhp67A%3d%3d; LIN=LING=NESAWda%2fRULSF3FWeGqMcgHDoHW28cG4KCW179YTMN8bEN9BtsXH%2b7LaiEGUxxv4HPM&AI=NESeOgDjyTK8Vkv9lSybOSQMQ%3d%3d&OSI=NESDdu2T7V54NiKPv2wfhp67A%3d%3d; mboxEdgeCluster=17; token=cpNu40BPIyPKxriplhGK7x5AxtOW; visit_id=1moqgnh8kra11e2ia8gqc1t5h5; ReferenceSessionCookie=02/14/2020 02:09:12 PM; GlobalSessionID=NESzs24CutmHio29Oghe6%2BTeJjSI0tCl1zA%2Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; TS01f74db7=01b041ad29ea1b40f12b84a67c868c9ef0e3eb9c8cb7bbdf0c0ca70c91cc1743ba2c274ab81421020546859cbb97fa58b56aa572c4bdfb97617cde635c79041047a2b3c8c6fcacc9a16d259ba2ac6c346ca441065f54b9c3c5234393725e2449f0da642826fb2a3f6d4e30bc8c468131d20c1c2ec12e0109db3f3fac1aa9c14e45e538dce02efacf00bb5561fb9b67ca571a3d27ba08587542b7f6176a20e8527129f14151ccd178a4a9b97165bfe5f76c5ee29206fa908fcdaacb99c4a82ac1bd8a4b22676a9ba3be51d3a7464631cfea5dd7d1e9; s_dfa=verizontelecomglobal; s_lastvisit=1581707352801; s_vnum=1612477505042%26vn%3D5; s_invisit=true; CUSTOMER_EXISTS=Y; rv-adobe=fios_rv%3D8054445%7C8065371%7C8619815%7C16032613%7C16393957%7C16435680; mbox=PC#314e9c7c414949918d013044bc6ce371.17_0#1644952194|session#e4d90ba8da20408ea53ef07253fbfee0#1581709212; AMCV_777B575E55828EBB7F000101%40AdobeOrg=-1891778711%7CMCIDTS%7C18307%7CMCMID%7C88733049013919627130901362749153428059%7CMCAAMLH-1582303930%7C7%7CMCAAMB-1582312194%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1581714552s%7CNONE%7CMCAID%7CNONE%7CMCCIDH%7C-21853914%7CvVersion%7C2.4.0; kampyleSessionPageCounter=2; AWSALB=DPIwEO2tTBtCyN9iT7A62fSGUaoQOi/ZhVY1U2TOIVyFCcqFkToFdR+lTC4Za4c1ttsmso2cTuXrTRdCLrABFUYPdvOcs+l+cSFL/hBxf4oFn5SxSf54T2vi4ucK; AWSALBCORS=DPIwEO2tTBtCyN9iT7A62fSGUaoQOi/ZhVY1U2TOIVyFCcqFkToFdR+lTC4Za4c1ttsmso2cTuXrTRdCLrABFUYPdvOcs+l+cSFL/hBxf4oFn5SxSf54T2vi4ucK; TS01c34141=01b041ad29f9072ab6cbb9f2e759705ee15d0eafe6b5c9f328ec1ae9650c02991a039e7148cc4ce30542e454f4cf5ab343a9c9950805a189d6cdfb3a87a927b326ea17670c242dea7a5c82ea1b31a8da680a9878b731b10792e1b45a3848f545aec3fd2effd7b18fbefeeac300dd0a0a37c059413ac9f17be67c620e4286e7cbdd80ee879b; TS6dd8a9c2027=08301e3d4aab2000b6f6a124a989c961804118b40292b5f5281bfe75fc4af5ac248ff08ea708600408c82437e7113000d6836000cdd6f85b04737d9bcdffe8aa217dd1e2a73f431d4e4e27d7ef09434f1cec3ae33f3dc2b2e0d0a5c2fca5cd71; SC_LINK=%5B%5BB%5D%5D; s_nr=1581707432972-Repeat; gpv_p17=res%7C%20lq%20address%20verification
					'Host': 'www.verizon.com',
					'Referer': 'https://www.verizon.com/inhome/qualification',
					'Sec-Fetch-Mode': 'navigate',
					'Sec-Fetch-Site': 'same-origin',
					'Sec-Fetch-User': '?1',
					'Upgrade-Insecure-Requests': '1',
					'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
				}

				r = s.get(url=url,headers=headers)
				print('buildhsi')
				url = 'https://www.verizon.com/foryourhome/ordering/ordernew/buildhsi.aspx'
				headers = {
					'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
					'Accept-Encoding': 'gzip, deflate, br',
					'Accept-Language': 'en-US,en;q=0.9',
					'Connection': 'keep-alive',
					'Authorization': 'Bearer ' + token ,
					#'Cookie': 's_sq=%5B%5BB%5D%5D; qualification=seg%3D7087294%2Cseg%3D7195725; aam_uuid=88749760752721138490904160119360806587; AkaSTrackingID=8f35f2614ed40577a51911dcd0f85858; AMCVS_777B575E55828EBB7F000101%40AdobeOrg=1; s_ecid=MCMID%7C88733049013919627130901362749153428059; check=true; _cls_v=0fd86e33-1845-435b-898b-380be562bb56; _cls_s=3c1c58f9-4d46-45e7-8bdd-c786ce4d0044:0; kampyle_userid=686b-3f28-96ce-e0f9-50a0-57d8-1ac3-cc65; _ga=GA1.2.29506293.1580941508; cd_user_id=1701774ff051ca-07f97546e34131-39647b09-13c680-1701774ff06742; s_cc=true; visitor_id=NESzs24CutmHio29Oghe6%2BTeJjSI0tCl1zA%2Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; chat_gsid=NESzs24CutmHio29Oghe6%252BTeJjSI0tCl1zA%252Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; ASP.NET_SessionId=z2wvu00yypc1e3logjhspo5w; VZ_ATLAS_SITE_PERS=BusinessUnit=residential; NESzs24CutmHio29Oghe6%2BTeJjSI0tCl1zA%2Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; UST=et=2020-2-14&c=1; _gid=GA1.2.423891174.1581699133; kampyleUserSession=1581699232504; kampyleUserSessionsCount=4; kampyleSessionPageCounter=1; TC_CHAT_IN_PROGRESS=; s_vnum=1612477505042%26vn%3D4; s_invisit=true; XSRF-TOKEN=4E45533936316A4A736868715176537739414E3075552F4269544167717373527762777337754D4A5575617A706D786E4737733766526238516E662F56624A72746642; EOrdering=isatom=N&DTP=D&TPXPSINFO=&PSF=&DOON=&RVD=&RVDT=&VF=&_e_=NESDdu2T7V54NiKPv2wfhp67A%3d%3d; LIN=LING=NESAWda%2fRULSF3FWeGqMcgHDoHW28cG4KCW179YTMN8bEN9BtsXH%2b7LaiEGUxxv4HPM&AI=NESeOgDjyTK8Vkv9lSybOSQMQ%3d%3d&OSI=NESDdu2T7V54NiKPv2wfhp67A%3d%3d; mbox=PC#314e9c7c414949918d013044bc6ce371.17_0#1644947697|session#904411e98ec243ffb0de1ed4c08c09c9#1581703788; token=7SPDRcThq2RJRGAlppPt6v3FNz60; CUSTOMER_EXISTS=Y; AMCV_777B575E55828EBB7F000101%40AdobeOrg=-1891778711%7CMCIDTS%7C18307%7CMCMID%7C88733049013919627130901362749153428059%7CMCAAMLH-1582303930%7C7%7CMCAAMB-1582308358%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1581706330s%7CNONE%7CMCAID%7CNONE%7CMCCIDH%7C-2038820344%7CvVersion%7C2.4.0; visit_id=n7ac8sc1tginp52d9101vqsto; ReferenceSessionCookie=02/14/2020 01:33:31 PM; s_lastvisit=1581705212759; rv-adobe=fios_rv%3D8054445%7C8619815%7C16032613%7C16393957%7C16435680; SC_LINK=%5B%5BB%5D%5D; s_nr=1581705252992-Repeat; gpv_p17=res%7C%20lq%20address%20verification; AWSALB=vgZhTI1VQJYktpK6md+EDYISNe96C4TXCEPaUrm5b7cZwHwpsy9Wp5ChEPFtpPe9DrQOZc1J/dY3/PGjnA1LntOlcQ32xE01Ieiqy0fiSxZ82masEu0eHpz14QFj; AWSALBCORS=vgZhTI1VQJYktpK6md+EDYISNe96C4TXCEPaUrm5b7cZwHwpsy9Wp5ChEPFtpPe9DrQOZc1J/dY3/PGjnA1LntOlcQ32xE01Ieiqy0fiSxZ82masEu0eHpz14QFj; GlobalSessionID=NESzs24CutmHio29Oghe6%2bTeJjSI0tCl1zA%2fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; TS01c34141=01b041ad2920f76d5af135c8764d3060e49a15ab5c268cd56ae201d451e69d392dba2a194818da4c8f6d5336c15f6d731d521f0ded4e75150609f4b7bacc8d3350dbf7577b286f44f5b0a7ee7e9985b45f48fb81a0d65f2d94ac3055767da70f9e93ce71c0461228b17201c6fd86f61ef5368b70c792b4dec3ffa1506d9443c3336684fd2f; TS01f74db7=01b041ad293341bb47d2f629659e9ccec12b39513bb7bbdf0c0ca70c91cc1743ba2c274ab81421020546859cbb97fa58b56aa572c4bdfb97617cde635c79041047a2b3c8c6fcacc9a16d259ba2ac6c346ca441065f757689d5d4324aa6c2c79737b81fe401c3d385559f6544d3f09af104c5d9495cf8cd44fbaa3f40bf89fb93492b22822e66307cb2d898875a867d5d3c35aa37b416d764c61b3079285852b4bc2894805fa295379ee7264ee90f6714f68cc198428cf660d61ccbaaf4b72f69f186b7b2e99f27d32b2d18f25d4f767f176478f79d; TS6dd8a9c2027=08301e3d4aab2000d8d5837d7dc4c9579dee4bce48a777545aa1b4864f0b60ccc1e84b0ca85ebf2a083d4bd8ee113000b8167e75328c3e687cb226d2d19e672c2680eee333d7e3ca40d1947bf1c98533ceb3a3de1ff45a04b4624f410c28e352',
					'Host': 'www.verizon.com',
					'Referer': 'https://www.verizon.com/inhome/qualification?',
					'Sec-Fetch-Mode': 'navigate',
					'Sec-Fetch-Site': 'same-origin',
					'Sec-Fetch-User': '?1',
					'Upgrade-Insecure-Requests': '1',
					'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
				}
				r = s.get(url=url,headers=headers)

				print(r.status_code)
				soup = BeautifulSoup(r.text, "html.parser")

				if debug == True:
					print(soup.prettify())

				print('fios')
				url = 'https://www.verizon.com/foryourhome/ordering/Services/Bundles/InitBuildFios'

				r = s.get(url=url)

				pp.pprint(r.json())


				url = 'https://www.verizon.com/foryourhome/ordering/Services/GetAllProducts'

				headers = {
					'Accept': 'application/json, text/plain, */*',
					'Accept-Encoding': 'gzip, deflate, br',
					'Accept-Language': 'en-US,en;q=0.9',
					'Authorization': 'Bearer ' + token ,
					'Connection': 'keep-alive',
					#'Cookie': 's_sq=%5B%5BB%5D%5D; qualification=seg%3D7087294%2Cseg%3D7195725; aam_uuid=88749760752721138490904160119360806587; AkaSTrackingID=8f35f2614ed40577a51911dcd0f85858; AMCVS_777B575E55828EBB7F000101%40AdobeOrg=1; s_ecid=MCMID%7C88733049013919627130901362749153428059; check=true; _cls_v=0fd86e33-1845-435b-898b-380be562bb56; _cls_s=3c1c58f9-4d46-45e7-8bdd-c786ce4d0044:0; kampyle_userid=686b-3f28-96ce-e0f9-50a0-57d8-1ac3-cc65; _ga=GA1.2.29506293.1580941508; cd_user_id=1701774ff051ca-07f97546e34131-39647b09-13c680-1701774ff06742; s_cc=true; visitor_id=NESzs24CutmHio29Oghe6%2BTeJjSI0tCl1zA%2Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; chat_gsid=NESzs24CutmHio29Oghe6%252BTeJjSI0tCl1zA%252Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; ASP.NET_SessionId=z2wvu00yypc1e3logjhspo5w; VZ_ATLAS_SITE_PERS=BusinessUnit=residential; NESzs24CutmHio29Oghe6%2BTeJjSI0tCl1zA%2Fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; UST=et=2020-2-14&c=1; _gid=GA1.2.423891174.1581699133; kampyleUserSession=1581699232504; kampyleUserSessionsCount=4; kampyleSessionPageCounter=1; TC_CHAT_IN_PROGRESS=; s_vnum=1612477505042%26vn%3D4; s_invisit=true; XSRF-TOKEN=4E45533936316A4A736868715176537739414E3075552F4269544167717373527762777337754D4A5575617A706D786E4737733766526238516E662F56624A72746642; EOrdering=isatom=N&DTP=D&TPXPSINFO=&PSF=&DOON=&RVD=&RVDT=&VF=&_e_=NESDdu2T7V54NiKPv2wfhp67A%3d%3d; LIN=LING=NESAWda%2fRULSF3FWeGqMcgHDoHW28cG4KCW179YTMN8bEN9BtsXH%2b7LaiEGUxxv4HPM&AI=NESeOgDjyTK8Vkv9lSybOSQMQ%3d%3d&OSI=NESDdu2T7V54NiKPv2wfhp67A%3d%3d; mbox=PC#314e9c7c414949918d013044bc6ce371.17_0#1644947697|session#904411e98ec243ffb0de1ed4c08c09c9#1581703788; token=7SPDRcThq2RJRGAlppPt6v3FNz60; CUSTOMER_EXISTS=Y; AMCV_777B575E55828EBB7F000101%40AdobeOrg=-1891778711%7CMCIDTS%7C18307%7CMCMID%7C88733049013919627130901362749153428059%7CMCAAMLH-1582303930%7C7%7CMCAAMB-1582308358%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1581706330s%7CNONE%7CMCAID%7CNONE%7CMCCIDH%7C-2038820344%7CvVersion%7C2.4.0; visit_id=n7ac8sc1tginp52d9101vqsto; ReferenceSessionCookie=02/14/2020 01:33:31 PM; s_lastvisit=1581705212759; rv-adobe=fios_rv%3D8054445%7C8619815%7C16032613%7C16393957%7C16435680; SC_LINK=%5B%5BB%5D%5D; s_nr=1581705252992-Repeat; gpv_p17=res%7C%20lq%20address%20verification; GlobalSessionID=NESzs24CutmHio29Oghe6%2bTeJjSI0tCl1zA%2fm0U98X6vjzXa6R3bA8zvCm5CzeyrbOZ; TS01f74db7=01b041ad293341bb47d2f629659e9ccec12b39513bb7bbdf0c0ca70c91cc1743ba2c274ab81421020546859cbb97fa58b56aa572c4bdfb97617cde635c79041047a2b3c8c6fcacc9a16d259ba2ac6c346ca441065f757689d5d4324aa6c2c79737b81fe401c3d385559f6544d3f09af104c5d9495cf8cd44fbaa3f40bf89fb93492b22822e66307cb2d898875a867d5d3c35aa37b416d764c61b3079285852b4bc2894805fa295379ee7264ee90f6714f68cc198428cf660d61ccbaaf4b72f69f186b7b2e99f27d32b2d18f25d4f767f176478f79d; AWSALB=0taP8nBqVpsymvNQMOdYbpRSUarUIZzeeajrA477+8JUa226qNI1stVfyjbDgrqiISSJDPPDk9KWjcKuKt8Yv05HHFuMT3efMMGf/WhyWbwJcqJKhgxjhfdSoMAm; AWSALBCORS=0taP8nBqVpsymvNQMOdYbpRSUarUIZzeeajrA477+8JUa226qNI1stVfyjbDgrqiISSJDPPDk9KWjcKuKt8Yv05HHFuMT3efMMGf/WhyWbwJcqJKhgxjhfdSoMAm; TS01c34141=01b041ad29b908305b0f2b7ab24d02ecfb20aa2317268cd56ae201d451e69d392dba2a194818da4c8f6d5336c15f6d731d521f0ded86d5657e253df084b9c751e4dc99d71ad7e7608ab928f6fe0118cb7a07d532de40725a676aa20a81cc8d6226037b59c95de4da11e48b366053efb25662ab8aebfce566478c9391004073003bdc6b1c3b; TS6dd8a9c2027=08301e3d4aab20006950a84d307995f555c441d4337eb1fad1226a6bbd9b67eec3b9041ba121e4910801d3738f113000a0b66a674aab1b227cb226d2d19e672c2680eee333d7e3ca40d1947bf1c98533ceb3a3de1ff45a04b4624f410c28e352',
					'Host': 'www.verizon.com',
					'Referer': 'https://www.verizon.com/foryourhome/ordering/ordernew/buildhsi.aspx',
					'Sec-Fetch-Mode': 'cors',
					'Sec-Fetch-Site': 'same-origin',
					'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
					#'X-NewRelic-ID': 'VQcEVF5bABADVFlWAwUEU1I=',
					#'X-XSRF-TOKEN': '4E45533936316A4A736868715176537739414E3075552F4269544167717373527762777337754D4A5575617A706D786E4737733766526238516E662F56624A72746642',
				}

				#pp.pprint(s.cookies)

				r = s.get(url=url, headers=headers)

				print('here')
				pp.pprint(r.json())
				'''

			return coverages

		# ISP: Windstream
		elif isp == 'windstream':

			s = requests.session()

			url = 'https://www.windstream.com/windstreamapi/PlutGeo/ServicablityByCityState?city=' + address.city + '&state=' + address.state

			headers = {
				'Accept': '*/*',
				'Accept-Encoding': 'gzip, deflate, br',
				'Accept-Language': 'en-US,en;q=0.9',
				'Connection': 'keep-alive',
				'Host': 'www.windstream.com',
				'Referer': 'https://www.windstream.com/high-speed-internet',
				'Sec-Fetch-Dest': 'empty',
				'Sec-Fetch-Mode': 'cors',
				'Sec-Fetch-Site': 'same-origin',
				'User-Agent': user_agent,
				'X-Requested-With': 'XMLHttpRequest',
			}

			r = s.get(url = url, headers=headers)
			response = r.json()
			if debug == True:
				print('CITY/STATE COVERAGE:')
				pp.pprint(response)

			if response.get('response').get('success') != True:
				return CoverageResult(is_covered=RESPONSES['windstream']['WE_CANT_FIND_ZIP'])
			else:
				url = 'https://www.windstream.com/windstreamapi/CheckServicability/UqualValidateAddress'
				data = {
					'street': address.line1,
					'city': address.city,
					'state': address.state,
					'zip': address.zipcode,
					'unitNumber': '', 
					'force': 'false',
					'unitDesignator': '',
					'streetPredirection': '', 
				}
				r = s.post(url = url, data=data, headers=headers)
				response = r.json()
				
				if debug == True:
					print("COVERAGE:")
					pp.pprint(response)

				data = response.get('response')
				if data.get('ValidationResult') == 'AddressFound':
					if len(data.get('dslQualificationResponse')) != 1:
						return CoverageResult(is_covered=101)

					if data.get('MaxQualSpeed') == 0:
						return CoverageResult(is_covered=RESPONSES['windstream']['NO_INTERNET'])
					else:
						return CoverageResult(is_covered=COVERED_GENERAL,max_downspeed=data.get('MaxQualSpeed'))
				elif data.get('ValidationResult') == 'AddressNotFound':
					# If there's an apartment number, try again without it
					if address.apt_number != '' and retries < 3:
						address.apt_number = ''
						return self.make_request(isp=isp, address=address, debug=debug, proxy=proxy, retries=retries+1)
					else:
						return CoverageResult(is_covered=RESPONSES['windstream']['WE_CANT_FIND_ADDRESS'])
				elif data.get('ValidationResult') == 'ZipCodeNotFound':
					# If there's an apartment number, try again without it
					if address.apt_number != '' and retries < 3:
						address.apt_number = ''
						return self.make_request(isp=isp, address=address, debug=debug, proxy=proxy, retries=retries+1)
					else:
						return CoverageResult(is_covered=RESPONSES['windstream']['ZIP_CODE_NOT_FOUND_CALL'])
				elif data.get('ValidationResult') == 'UQualDbNotReachable':
					return CoverageResult(is_covered = RESPONSES['windstream']['UQAL_NOT_REACHABLE'])
				else:
					return CoverageResult(is_covered=100)

		# ISP: XFinity 
		# This part of the tool used to work, but now gets uniformly rate-limited
		elif isp == 'xfinity':

			s = requests.session()

			# Get location ID
			url = 'https://www.xfinity.com/learn/api/neptune/address-search/suggestions?search=' + address.line1 + '&showMore=true'
			url = url.replace(' ','+')

			headers = {
				'user-agent':user_agent,
				'accept': 'application/json, text/plain, */*',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
				'adrum': 'isAjax:false',
				#'cookie': r'ADRUM=s=1589918082820&r=https%3A%2F%2Fwww.xfinity.com%2Flocations%2Fin-my-area%3F0; PSC=UCID=060d1efe-aee4-404c-9847-5df6eb803de1&CTY=Princeton&ST=NJ&Z=08540&RC.MKT=13560; SC=RC.USID=fee8d365-fbce-40ed-8c3f-107856b5d645&VA=1025&CTY=Princeton&ST=NJ&Z=08540&GEO=True&RC.MKT=13560&L1ID=11599&L2ID=1187&L3ID=265&L4ID=13468; ASP.NET_SessionId=wqpvvgfe2peesp12glncctmc; SC_ANALYTICS_GLOBAL_COOKIE=9c39d0546c7a410985b8a7edd3a54581|False; www-prd_ch=NMANJGKC; AKA_A2=A; bm_sz=E82738A22B8AC11B448E0B3E011A997D~YAAQHFoauOgzgilyAQAAcamALgedOc9tEwoLiN/tArl1RoR97YJrKjkIOd6y2K6Kd4nJw1wCZSfMvG+ilL6s8iZvc97yBjWwZCPcjJgKtHywsA+FRdpmRUfEI+cR/mViwKNQEXX8c2W2BaSaNWs/qiyLKGqhHVqE1r09W0QvcWWk35BQGUoSCTr252ZQx4NPLQ==; check=true; AMCVS_DA11332E5321D0550A490D45%40AdobeOrg=1; AMCV_DA11332E5321D0550A490D45%40AdobeOrg=-1712354808%7CMCIDTS%7C18402%7CMCMID%7C51393300678773604611761550336054447001%7CMCAAMLH-1590522884%7C7%7CMCAAMB-1590522884%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1589925284s%7CNONE%7CMCAID%7C2F2F6A168515F6EA-6000084AA265A365%7CvVersion%7C4.3.0; _abck=59A625B814EB066EE992A33FC778F96A~0~YAAQHFoauGo1gilyAQAAlrKALgP+vnl04VJBjjv/80Lrd54m9zSmQR8g2SVxusJwoPVQeQQcU5QqQ7h6IX4YIFktvOWZ1s7nKVvwXjwtEgGdg4dGlZwlXO6sPt90NtJSRabDpE2W8Uej3hOKQt69zhwfgHvoZ7mqW7Rfy4Wra8EO4qfvUaRcfeFjYYswY41RQorhc9pqFsNaDr5NTx0GcbFFOugfzs4rKklbOI9FDNvSC/b7toNWrckKJD2lty2Mbr1y/K4yj3WIxGNmpc2AYFgA+Rsm4i5TIQtr8HlaqrmZZIzX4JrSR0/XoRi3g+QogatYzqFdKxQ=~-1~-1~-1; ak_bmsc=9688BB6B67DDE8F864C60AD8F51967BBB81A5A1CD96D00008339C45EFAB6EA39~plfNJBJIOvdSuagcdiAmeEvb5PIY9MLD1HX8Qno8mga1qPXJsqycaD92WsvsCKd96Hdy8uNkYRoaBkww5e91tClSCpSCSnJPYF7dMLX0J7cvpmi8s9KOJKeL1ki5IHr/CwUgthl/EUrpdpr0o8NHMjLLUCPU79fdL9ivxlaVek2xuJ/YCxQA9iLvEQicy/Ju1GRaws2PcYcMHG3n3kdtLgXGnpQpJWJFGjRvt6QaIVsGcxJGRAzPSHkQtXUSHrPhBE; s_sess=%20s_ttc_ev87%3D1589918087464%3B%20s_cc%3Dtrue%3B; _uetsid=089569c7-4554-51e4-950d-b27ca42b0ba0; IR_gbd=xfinity.com; IR_8543=1589918089316%7C0%7C1589918089316%7C%7C; _gcl_au=1.1.1979574038.1589918090; _ga=GA1.2.1142565253.1589918090; _gid=GA1.2.1719159832.1589918090; _fbp=fb.1.1589918089793.1453179654; mbox=session#06ba33ad4b464de88230911f6a69c66a#1589919950; _gat=1; AAMC_comcast_0=REGION%7C7; fltk=segID%3D2450016%2CsegID%3D6761408%2CsegID%3D6761294%2CsegID%3D6759340%2CsegID%3D2056160%2CsegID%3D1662899%2CsegID%3D12965809; aam_sitecore=metro%3Dct_new_york%2Cmetro%3Dde_philadelphia%2Cmetro%3Dms_jackson%2Cexisting_customer%3Dtrue%2C1947324%3Dy%2C1898505%3Dy%2C1296524%3Dy%2C1915698%3Dy%2C2064043%3Dy%2C2450016%3Dy%2C2506414%3Dy%2C2506411%3Dy%2C2506406%3Dy%2C2818943%3Dy%2C2802245%3Dy%2C2802247%3Dy%2C2056160%3Dy%2C2064654%3Dy%2C2069065%3Dy%2C2802245%3Dy%2C2802247%3Dy; aam_uuid=51230999057439989541745199821450114878; QuantumMetricUserID=0399238198e0c138f42983890f3957b3; QuantumMetricSessionID=cbb11adf3e58b97eac02c19dace411fc; ipe.22299.pageViewedCount=0; ipe.22299.pageViewedDay=140; ipe_22299_fov={"numberOfVisits":1,"sessionId":"13c2558d-f9e6-0ac5-fbf6-b1354c666417","expiry":"2020-06-18T19:54:58.585Z","lastVisit":"2020-05-19T19:54:58.585Z"}; ipe_v=9f540253-52e5-bff5-169a-d6c0829a31eb; IPE_Campaign=no_campaign; ipe_s=5577a4c8-8e76-adfc-0a88-a77267d8758a; bm_sv=C4E09F3554BBB332F0B56B4D09A8EF60~x3j02Zl5qVTQsFMxUouPfJ2ZuRcRvpDkPRoMeR9q8F06074Q5e3NH1BMgf94jJfwclUxwtiK9ArM08KE98YvfbUyPWzo6kOGM591js/bf7tBWHvJzeA/8ZCnSNTDl5lpAcW/EGctl3qCHA+s+L+r5ybDptQquXn0tn0d4B0zYrw=; s_pers=%20s_dfa%3Dcomcastdotcomprod%7C1589919886289%3B%20gpv_Page%3Dresi%257Csales%257Clocal%257Carea%257Cmy-area%257Cbundles%7C1589919898287%3B%20stc18%3D%7C1589919904481%3B%20s_lv%3D1589918104492%7C1684526104492%3B%20s_lv_s%3DFirst%2520Visit%7C1589919904492%3B; s_sq=comcastdotcomprod%3D%2526c.%2526a.%2526activitymap.%2526page%253Dhttps%25253A%25252F%25252Fwww.xfinity.com%25252Flocations%25252Fin-my-area%2526link%253DContinue%2526region%253DBODY%2526.activitymap%2526.a%2526.c%2526pid%253Dhttps%25253A%25252F%25252Fwww.xfinity.com%25252Flocations%25252Fin-my-area%2526oid%253DContinue%2526oidt%253D3%2526ot%253DSUBMIT',
				'referer': 'https://www.xfinity.com/locations/in-my-area',
				'sec-fetch-dest': 'empty',
				'sec-fetch-mode': 'cors',
				'sec-fetch-site': 'same-origin',
				#'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36',
			}
			r = s.get(url = url,headers=headers,proxies=proxies)
			if r.status_code == 403:
				raise Exception("1. Got 403 error when trying to get location")
			response = r.json()

			if debug == True:
				print(url)
				print('ADDRESS SEARCH')
				pp.pprint(response)
	
			location_id = ''
			apt_type = ''
			apt_number = ''

			for address_info in response.get('Data'):
				# Only take Id if Id exists and the suggested address's street address and zip code are the same as our's
				if address_info.get('Address').get('Address_StreetAddress') == address.line1 and address_info.get('Address').get('Address_ZipCode') == address.zipcode and address_info.get('Address').get('Address_LocationId') != '':
					# Pick the apt of the first suggested address that matches our's (we're just picking a random unit in the building)
					location_id = address_info.get('Address').get('Address_LocationId')
					apt_type = address_info.get('Address').get('Address_UnitType')
					apt_number = address_info.get('Address').get('Address_UnitNumber')
					break

			# Just to make apt number and type consistent (the xfinity API returns None and not '')
			if apt_type == None:
				apt_type = ''
			if apt_number == None:
				apt_number = ''
			
			if debug == True:
				print('LOCATION ID: ' + location_id)
				print(apt_type)
				print(apt_number)

			url = 'https://www.xfinity.com/learn/api/neptune/localize'

			# Create body and add addresss-specific parameters
			body = {
				"Address": {
					"IsRequestFromSingleAddressField":"true",
					"SalesSessionId": "",
					"SearchReferenceId": "",
					"Over25.unitNumber":"",
				},
				"Address_MDU_Units": "",
				"FullAddress": "",
				"OfferId": "",
				"PageName": "",
				"RedirectURL": "reload",
				"RedirectionType": "",
				"Source": "",
				"TenantInfo" : {
					"Affiliate": "",
					"AgentNTID": "",
					"AvayaAgentId": "",
					"CSGOperatorId": "",
					"CSGSalesRepId": "",
					"Channel": "",
					"ConsumerType": "",
					"DDPOperatorId": "",
					"DDPSalesRepId": "",
					"Flavor": "",
					"Issuer": "",
					"OmniConsumerType": "",
					"StoreId": "",
					"UId": "",
					"UcId": "",
				},
				"idIsSingleInputFallbackSituation": "",
				"idOriginalBeforeFallbackHeader": "",
				"idOriginalBeforeFallbackSubheader": "",
				"isDirectLinking": "False",
			}
			body["Address"]["SingleStreetAddress"] = address.line1 + ", " + address.city + ", " + address.state + " " + address.zipcode
			body["Address"]["StreetAddress"] = address.line1
			body["Address"]['zipcode'] = address.zipcode
			if location_id != '':
				body["Address"]['LocationId'] = location_id
			if apt_type != '':
				body["Address"]["UnitType"] = apt_type
				body["Address"]["UnitNumber"] = apt_number
			else:
				body["Address"]["UnitType"] = ''
				body["Address"]["UnitNumber"] = ''

			# Make request
			headers = {
				'accept': 'application/json, text/plain, */*',
				'accept-encoding': 'gzip, deflate, br',
				'accept-language': 'en-US,en;q=0.9',
				'content-type': 'application/json;charset=UTF-8',
				'cookie': r'ASP.NET_SessionId=pwzeyw5wfegguvz23znrsl2c; SC_ANALYTICS_GLOBAL_COOKIE=74fb545832d14ebd866deb32f67aa292|False; check=true; AMCVS_DA11332E5321D0550A490D45%40AdobeOrg=1; ipe_s=951bc68b-c27f-3bf3-c2de-5234c2b585f9; QuantumMetricUserID=bb3ac11ab236b6985a0767484b607bcf; IR_gbd=xfinity.com; AAMC_comcast_0=REGION%7C7; aam_sc=aamsc%3D8163787; aam_uuid=51230999057439989541745199821450114878; _ga=GA1.2.757503275.1593805680; _gcl_au=1.1.1297193439.1593805680; _fbp=fb.1.1593805680760.979696246; IPE_Campaign=no_campaign; ipe_v=44dd0b16-e4b5-a10f-a22d-155fbdf5f102; aam_sitecore=metro%3Dct_new_york%2Cmetro%3Dde_philadelphia%2Cmetro%3Ddc_washington%2Cmetro%3Dms_jackson%2Cexisting_customer%3Dtrue%2C1898505%3Dy%2C1296524%3Dy%2C2064043%3Dy%2C2450016%3Dy%2C2506406%3Dy%2C2818943%3Dy%2C2802245%3Dy%2C2802247%3Dy%2C2056160%3Dy%2C2745468%3Dy%2C2802245%3Dy%2C2802247%3Dy; QuantumMetricSessionID=9603bb01e5e3109fc9c2947cd850a6a1; www-prd_wc=LEBLFHEE; AKA_A2=A; bm_sz=F637B594C8D8CB5F42CBC010D727732A~YAAQDWAZuPKg/ulzAQAAcCV4+AhfwkjTxg5x38gsYymqs1Ao/jqxkIRci0lYpBPm/PiZ1GdQRB7hbGNIFkGpsuIr5rMQUDwnuArk7rGyqK1grdJU3xR3OPD1sljipffL2LbE0nWxmdqrEGYv8ES2Qp/18bN2fngd6Dq3/R/acILxWCw/ZA7k0LIKn66qTXdD; ak_bmsc=FE40E2A2B743F6163E321AC04D57A9C9B819600DE11E0000D276395FA5C4D73E~plXEi0QTj/3133kPzeEfMBTQkQo/YqrDxAwrhbCkb6OPxccyjM8DvumSUtysLA5zLXhz+mbO5hSJG2SCREE8KaQhKixY1I3FOXzK/CMsaRnJuHLWwlQlskY019aohlq1QEuTNQEd+6ulRKhug9vt6f3CVn9NgWxJEH3BcATDvwLDQmV6sR8R4hAqoMujus8sJtNWXc6lBGjaUzNQ78HLRoprwxetAOTUL40Hxzn38ToOjL2pQd03bYRGf77ioatiN5; ipe.22299.pageViewedDay=229; _gid=GA1.2.1424399153.1597601499; fltk=segID%3D2450016%2CsegID%3D6761408%2CsegID%3D6761294%2CsegID%3D6759340%2CsegID%3D2056160%2CsegID%3D12965809; bounceClientVisit1369v=N4IgNgDiBcIBYBcEQM4FIDMBBNAmAYnvgO6kB0AHgGYCWAdjQgJ5kDGA9gLZFgCmAhgCc6PfnQAm9AOZF2AVwQBadlUVV27ZIPoJM+AMoJBvXgizjxxlOgwARAJwA2PAFZcABgDCAeQByAcQAlAFF9fVcPfQAVPEcsCCEETl46XTssAAUY3Dd3AEZYgC0aCE92cV5MW3z7AHZ3EAAaEEEYEFJiSloGZjYuEABfIA; _abck=BBB26F8A80B86D06DFB960E458193A97~0~YAAQDWAZuNOq/ulzAQAAkv95+AT+9QUvVYQ0GB6Yzjm2GSkcwgKb+SaPg30wznY/Z6ho9taZHuvP3vlmoENF5eQI9ogeaVd0U5W+Q+VixHG4HDaQVStr6DqBytdyjFHv4UtVtghtiCK4V1l7gyHdYM6Yjj+TB9cLDAKpd4PhnmFrQWLgog3ZDiXJOquf+IJeplSXnyn/KNtDNfDpJeYbq9n25fOEXloOoXtVXWKMevl6ai7vsks6Vo0HXNoZXkFdW0CxU2PWg04qiTq+MjeX3/FSx/cCTHnDI22kctQnkdD2LeBiBh6DegAVAFVT9+lzJJ7FLmtCk8g=~-1~-1~-1; SC=RC.USID=7d7fbc47-ffe3-451d-b418-9403b9a4a621&VA=34817&RC.IFL=Y&RC.LOC=233423993&L1ID=11599&L2ID=5051&L3ID=6132&L4ID=3846&RC.SP=699c2449-c2c7-422a-bdd6-9f82f12dc8ee&CTY=METHUEN&ST=MA&RC.MKT=6114&RC.BIL=CSG&RC.SYS=8773&RC.PRIN=1000&RC.AGT=2490&RC.CORP=0&RC.CRPN=0&RC.FRCH=0&RC.FRCHN=2490&RC.HK=1E09EF8851E2840AF9D4414F377B5E6A&Z=01844&RC.IPL=N; PSC=UCID=35b542d7-5a9f-43c8-abde-ea9603408856&CTY=METHUEN&ST=MA&Z=01844&RC.MKT=6114&RC.RLOC=233423993&REC=N&EX=False; s_sess=%20s_ttc_ev87%3D1597601629835%3B%20s_cc%3Dtrue%3B; AMCV_DA11332E5321D0550A490D45%40AdobeOrg=-1712354808%7CMCIDTS%7C18491%7CMCMID%7C51393300678773604611761550336054447001%7CMCAAMLH-1598206430%7C7%7CMCAAMB-1598206430%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1597608830s%7CNONE%7CMCAID%7C2F2F6A168515F6EA-6000084AA265A365%7CvVersion%7C4.3.0%7CMCCIDH%7C788371218; ADRUM=s=1597601692454&r=https%3A%2F%2Fwww.xfinity.com%2Flearn%2Foffers%3F0; mbox=session#5045eaca453f4da0a72e3792e1827b9b#1597603554; _uetsid=29e13f06f9612236113d2a9ce05d2c07; _uetvid=6b5377263e05e9108fd8882a1cb031c2; IR_8543=1597601695078%7C0%7C1597601494592%7C%7C; _gat=1; ipe.22299.pageViewedCount=9; ipe_22299_fov={"numberOfVisits":1,"sessionId":"951bc68b-c27f-3bf3-c2de-5234c2b585f9","expiry":"2020-09-15T18:11:35.375Z","lastVisit":"2020-08-16T18:14:56.517Z"}; bm_sv=C470A4C989B3DCC3EEF6917A807C6861~VhyFMLTAgrLLjmtS3OYrf/ImvsbBl0AaZku/dbxh/Phueim2Rp+katXETu+CGr04WdN8o6yWXNopDU4WAKWbU6ppmJyRvJ05Cwfuw4yIbmNNHf2FC9UmGrifnGi6+XnrHMXAzrcITDdMwsF8t0qyMZWxwNqsDIVvJIuOELPqnBY=; s_pers=%20s_dfa%3Dcomcastdotcomprod%7C1597603493919%3B%20gpv_Page%3Dresi%257Csales%257Cshop%257Clearn%257Clocalization%257Center%2520address%7C1597603499387%3B%20stc18%3D%7C1597603507661%3B%20s_lv%3D1597601707673%7C1692209707673%3B%20s_lv_s%3DMore%2520than%25207%2520days%7C1597603507673%3B; s_sq=comcastdotcomprod%3D%2526c.%2526a.%2526activitymap.%2526page%253Dresi%25257Csales%25257Cshop%25257Clearn%25257Cout%252520of%252520footprint%2526link%253DContinue%2526region%253DBODY%2526pageIDType%253D1%2526.activitymap%2526.a%2526.c%2526pid%253Dresi%25257Csales%25257Cshop%25257Clearn%25257Cout%252520of%252520footprint%2526pidt%253D1%2526oid%253DContinue%2526oidt%253D3%2526ot%253DSUBMIT',
				'origin': 'https://www.xfinity.com',
				'referer': 'https://www.xfinity.com/locations/in-my-area',
				'sec-fetch-dest': 'empty',
				'sec-fetch-mode': 'cors',
				'sec-fetch-site': 'same-origin',
				'user-agent' : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36',#user_agent,
				#'cookie': 'SC_ANALYTICS_GLOBAL_COOKIE=a68ca012bef54650811790252ef569bb|False; _gcl_au=1.1.999842113.1582320523; _fbp=fb.1.1582320522825.212911589; QuantumMetricUserID=0399238198e0c138f42983890f3957b3; ipe_v=185d0c4f-2efa-898b-dc47-9993cd604f56; AAMC_comcast_0=REGION%7C7; aam_uuid=51230999057439989541745199821450114878; _ga=GA1.2.1683647772.1582320524; fltk=segID%3D2450016%2CsegID%3D6761408%2CsegID%3D6761294%2CsegID%3D6759340%2CsegID%3D2056160%2CsegID%3D12965809; ASP.NET_SessionId=oqmk5fmg3e3ucrrepjnj1sr3; check=true; AMCVS_DA11332E5321D0550A490D45%40AdobeOrg=1; IR_gbd=xfinity.com; ipe_s=5577a4c8-8e76-adfc-0a88-a77267d8758a; IPE_Campaign=no_campaign; aam_sitecore=metro%3Dct_new_york%2Cmetro%3Dde_philadelphia%2Cmetro%3Dms_jackson%2Cexisting_customer%3Dtrue%2C1947324%3Dy%2C1898505%3Dy%2C1296524%3Dy%2C1915698%3Dy%2C2064043%3Dy%2C2450016%3Dy%2C2506414%3Dy%2C2506411%3Dy%2C2506406%3Dy%2C2818943%3Dy%2C2802245%3Dy%2C2802247%3Dy%2C2056160%3Dy%2C2064654%3Dy%2C2069065%3Dy%2C2802245%3Dy%2C2802247%3Dy; PSC=UCID=da2e50bf-f86f-4c00-baa3-fb4b3c941165&CTY=KNOXVILLE&ST=TN&Z=37922&RC.MKT=14063&RC.RLOC=278061894&REC=N&EX=False; pulse_insights_udid=1329323b-1a9b-4249-aa1b-bbc2549b19fa; pi_pageview_count=1; pi_visit_track=true; pi_visit_count=2; ipe_planBuilder=true; _abck=A1D684E19B15AA9BFB030A21BE736BEE~0~YAAQi/NUuFCNxcBxAQAA6mdeFgOTf8aU4aUoe9Oz4d6ihjkkAoE7PTgWEm240UEf/90jvCleYOaJZ88g5G7POELjDUQbI3d5lAkfXhb3LNA3CoYhPAVVNsq512WatLaOxAvLo02WkQAA/Z1jlyllvMj8joN3lWj5zgrBiphWjGUBmrumk4/H+OVZXC1gozpfJyFiaKTw5eRNuu+yEhbvA6lFvG3TL31xPMe3C2RyMm9x2B6HBpXf8juw/kcY9Sbe8DRTMPDVb7JwA35IMpK351NHYHIvyQWiKt/azPZcUlMoE9yFaCIDyjD5UJlzEFjASN0UoQwcQ1c=~-1~-1~-1; ipe.22299.pageViewedCount=1; ADRUM=s=1589520094546&r=https%3A%2F%2Fwww.xfinity.com%2Flocations%2Fin-my-area%3F0; QuantumMetricSessionID=8fdbc3ba4cf2792337b90918bc344cd4; www-prd_wc=LKBLFHEE; bm_sz=849F8C0F2442CF2A23F9A3357AB03CD7~YAAQ0iv2SNAMeylyAQAAa2LMLQcIvrmGexi7Q6dXa99SCEWMNGAPzMhBUPv4u7CdfceSTwenZUfnZlvNIRLM9W2ce0iffH5rnf5GhprKdHUwvZJLxdh15RmF5Vr219uNlHOltUfQkt86Ygzhl59B/1PVu3AYqWUk7p2wZwksQ4GzLezpC8kAeRwSlajnx/MQEg==; AMCV_DA11332E5321D0550A490D45%40AdobeOrg=-1712354808%7CMCIDTS%7C18402%7CMCMID%7C51393300678773604611761550336054447001%7CMCAAMLH-1590511070%7C7%7CMCAAMB-1590511070%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1589913470s%7CNONE%7CMCAID%7CNONE%7CvVersion%7C4.3.0%7CMCCIDH%7C1931064449; ak_bmsc=E9D30DFBC98CE49BF3E85E7D361D97BD48F62BD2032500005C0BC45E1F26CD5F~plv5EgITuNNhloga2rDqH65X2SLz5X1Qy2yzS3XK+850kMOUeC84QnnXWAno4eUEfh6KEqEUKkVIsw8gwAlp9POfEviac+D+LNKFkeyMJN2ZxhojS3mw96nA0Z9iOxXhaymm9ZD1gZrjg8yloBflKGJj4hGqIIokWUPB0nZKHcq17XOm4pGEFVP36o07OJKne7Ea1Mf5jqs3KF6JXj3I2ie3TB/AUWLKrPFOE10IMyTAXwRm65Qjzq9d5dVdHb4DKQ; _uetsid=998de89c-af56-b502-04f4-06f472e7b9f5; IR_8543=1589906277124%7C0%7C1589906277124%7C%7C; SC=RC.USID=6e107d15-957c-4b2d-9f51-1b15041291ad&VA=34817&RC.IFL=Y&RC.LOC=278061894&L1ID=11592&L2ID=6342&L3ID=6343&L4ID=14042&RC.SP=a314c6b3-a9ab-4bdf-9281-eec56be24ee6&CTY=KNOXVILLE&ST=TN&RC.MKT=14063&RC.BIL=CSG&RC.SYS=8396&RC.PRIN=5000&RC.AGT=40&RC.CORP=0&RC.CRPN=0&RC.FRCH=0&RC.FRCHN=40&RC.HK=5BB1A0D8F39094D0E3266A1DA2597CB8&Z=37922; s_sess=%20s_ttc_ev87%3D1589906277513%3B%20s_cc%3Dtrue%3B; AKA_A2=A; _gid=GA1.2.913473278.1589906279; ipe.22299.pageViewedDay=140; ipe_22299_fov={"numberOfVisits":3,"sessionId":"5577a4c8-8e76-adfc-0a88-a77267d8758a","expiry":"2020-06-12T16:27:53.431Z","lastVisit":"2020-05-19T16:37:59.119Z"}; mbox=session#cad3f6390d2945c29ced5c515490b38d#1589908140; bm_sv=A458F0BC354D3C811072DBFA09DCA94F~ioBOvIVPpT1y2TwqT+y0p0IUKDxL98j71BQjSYgLdWb5gZh7/6H8S7/5X/RUDoGGdhHb7LO/rt0MByliFOu3yzgnj56TnUYjzb8xQme9CBRAvtoUO55bHR4Z9b0zZOVltTPlY1ue66g378qqJXpfYizl7Q4gYTCfLIuZd+sD060=; s_pers=%20s_dfa%3Dcomcastdotcomprod%7C1589908074859%3B%20stc18%3D%7C1589908160608%3B%20s_lv%3D1589906360686%7C1684514360686%3B%20s_lv_s%3DLess%2520than%25207%2520days%7C1589908160686%3B%20gpv_Page%3Dresi%257Csales%257Clocal%257Carea%257Cmy-area%257Cbundles%7C1589908160711%3B; s_sq=comcastdotcomprod%3D%2526c.%2526a.%2526activitymap.%2526page%253Dresi%25257Csales%25257Clocal%25257Carea%25257Cmy-area%25257Cbundles%2526link%253DContinue%2526region%253DBODY%2526pageIDType%253D1%2526.activitymap%2526.a%2526.c%2526pid%253Dresi%25257Csales%25257Clocal%25257Carea%25257Cmy-area%25257Cbundles%2526pidt%253D1%2526oid%253DContinue%2526oidt%253D3%2526ot%253DSUBMIT'
				#'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
			}

			r = s.post(url = url, data=body, headers=headers,proxies=proxies)

			if r.status_code == 403:
				raise Exception("2. Got 403 error")

			response = r.json()

			if debug == True:
				print('COVERAGE INFO')
				pp.pprint(response)
			data = response.get("Data")

			coverage_result = None

			if response.get('RedirectUrl') != None:
				if 'out-of-footprint' in response.get('RedirectUrl'):
					coverage_result = CoverageResult(is_covered = NOT_COVERED)
				elif 'active-address' in response.get('RedirectUrl'):
					coverage_result = CoverageResult(is_covered = COVERED_EXISTS)
				elif 'in-my-area' in response.get('RedirectUrl'):
					coverage_result = CoverageResult(is_covered = COVERED_NOT_EXISTS)
				elif 'business-location' in response.get('RedirectUrl'):
					coverage_result = CoverageResult(is_covered = BUSINESS)
				elif 'sorry' in response.get('RedirectUrl'):
					# redo the request
					if retries < 2:
						return self.make_request(isp=isp, address=address, debug=debug, retries=retries+1,proxy=proxy)
					else:
						return CoverageResult(is_covered = RESPONSES['xfinity']['SORRY'])
				elif 'extra-attention' in response.get('RedirectUrl'):
					coverage_result = CoverageResult(is_covered = RESPONSES['xfinity']['EXTRAATTENTION']) 
				elif 'bulk-tenant' in response.get('RedirectUrl'):
					return CoverageResult(is_covered = RESPONSES['xfinity']['BULKTENANT'])
				elif 'bulk-master' in response.get('RedirectUrl'):
					return CoverageResult(is_covered = RESPONSES['xfinity']['COMMUNITY'])
				else:
					coverage_result = CoverageResult(is_covered = UNKNOWN)
			else:
				if 'SimilarAddresses' in data and len(data.get('SimilarAddresses')) != 0:

					# This returns several apartments. Let's just choose one 
					entered_address = data.get('EnteredAddress').get('StreetAddress')
					suggested_address = data.get('ApiServiceResult').get('Result').get('CustomerProfile')[0].get('Address').get('StreetAddress1')
					
					# Confirming that the address they are suggesting is actually the same
					if entered_address != suggested_address:
						return CoverageResult(is_covered = UNKNOWN+3)

					apt_type = data.get('ApiServiceResult').get('Result').get('CustomerProfile')[0].get('Address').get('UnitType')
					if apt_type == None:
						apt_type = 'abcd'
					apt_number = data.get('ApiServiceResult').get('Result').get('CustomerProfile')[0].get('Address').get('UnitNumber')
					if apt_number == None:
						apt_number = 'abcd'

					if debug == True:
						print("NEW APT TYPE: " + apt_type)
						print("NEW APT NUMBER: " + apt_number)

					new_address = Address(
						firstline = address.line1,
						city = address.city,
						state = address.state,
						zipcode = address.zipcode,
						apt_type = apt_type,
						apt_number = apt_number
					)

					if retries < 1:
						result = self.make_request(isp='xfinity', address=new_address, debug=debug, retries=retries+1, proxy=proxy)
						return result
					else:
						coverage_result = CoverageResult(is_covered = UNKNOWN+4)
				elif 'ValidationIssues' in data:
					if 'The address you entered could not be recognized.' in data.get('ValidationIssues')[0].get('messages')[0]:
						coverage_result = CoverageResult(is_covered = NOT_RECOGNIZED)
					else:
						coverage_result = CoverageResult(is_covered = UNKNOWN+1)
				elif "EnteredAddress" in data:
					coverage_result = CoverageResult(is_covered = COVERED_NOT_EXISTS)
				else:
					coverage_result = CoverageResult(is_covered = UNKNOWN+2)
			
			return CoverageResult(is_covered = coverage_result.is_covered)

			'''
			# Incomplete code to get speed info

			if coverage_result.is_covered in [COVERED_EXISTS, COVERED_NOT_EXISTS]:
				address_id = data.get('ApiServiceResult').get('Result').get('MarketReference').get('LocationId')

				if address_id == None or address_id == '':
					print("NONE for address: " + address.fullAddress())
					return CoverageResult(is_covered = coverage_result.is_covered)

				url = 'https://www.xfinity.com/learn/offers/plan-builder/offers/modular/15140/tiers?days_ahead=0&location_id=' + address_id + '&channel=DOT_COM_POS'

				for i in range(3):

					r = s.get(url = url, proxies=proxies)

					if debug == True:
						print(r.status_code)

					if r.status_code == 200:
						response = r.json()

						#if debug == True:
						#	pp.pprint(response)

						plans = response.get('Internet')

						max_speed = -1
						for plan in plans:
							heading = plan.get('heading')
							speed = int(heading.split(' ')[0])

							if speed > max_speed:
								max_speed = speed

						return CoverageResult(is_covered = coverage_result.is_covered, max_downspeed=max_speed)

					# Case where it's the other plan builder. It seems to use some sort of cookie/session with the IP,
					# so I don't think we can get the speeds here.
					else:
						return CoverageResult(is_covered = coverage_result.is_covered)
						
						url = 'https://www.xfinity.com/learn/offers'

						r = s.get(url = url, proxies=proxies)

						soup = BeautifulSoup(r.text, "html.parser")

						#if debug == True:
						#	print(soup.prettify())

						data = json.loads(soup.find('script', id='r-offer-dealfinder').text)
						url = 'https://www.xfinity.com' + data.get('dataSource').get('url')

						r = s.get(url = url, proxies=proxies)
						response = r.json()

						if debug == True:
							pp.pprint(response)

						packages = response.get('Data').get('Results')

						max_upseed = -1
						max_downspeed = -1

						for package in packages:
							internet = package.get('InternetPackage')

							if internet != None:
								if internet.get('InternetDownloadSpeedMbps') > max_downspeed:
									max_downspeed = internet.get('InternetDownloadSpeedMbps')
								if internet.get('InternetUploadSpeedMbps') > max_upseed:
									max_upseed = internet.get('InternetUploadSpeedMbps')

						return CoverageResult(is_covered = coverage_result.is_covered, max_upspeed=max_upseed, max_downspeed=max_downspeed)
					
			else:
				return coverage_result
				'''

		else:
			print("We don't cover that ISP.")
			return None



