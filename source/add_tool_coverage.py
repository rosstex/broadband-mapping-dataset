from collections import defaultdict
import traceback
from datetime import datetime
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
import pandas as pd
import numpy as np
import requests
import csv
from IspApiTool import IspApiTool
from Address import Address
from CoverageResult import CoverageResult
import threading
import time
import sys
from  requests.exceptions import ProxyError
import pprint
import random
from UserAgents import user_agents_charter,user_agents_ipad
from calculate_statistics import is_known_res

pp = pprint.PrettyPrinter(indent=4)
state = sys.argv[2]

# --------------------------------------------------------------------------------------------------

# Connect to mysql database
mydb = mysql.connector.connect(
  host="localhost",
  user="root",
  passwd="",
  database="{}_addresses".format(state)
)


# Create cursor
mycursor = mydb.cursor(buffered=True)


isp_run = sys.argv[1]

proxy_choices = [
	#"us-wa.proxymesh.com:31280",
	"fr.proxymesh.com:31280", 
	"jp.proxymesh.com:31280", 
	"au.proxymesh.com:31280", 
	"uk.proxymesh.com:31280", 
	"nl.proxymesh.com:31280", 
	"sg.proxymesh.com:31280",
	"us-il.proxymesh.com:31280", 
	"us.proxymesh.com:31280", 
	"us-dc.proxymesh.com:31280", 
	"us-ca.proxymesh.com:31280", 
	"us-ny.proxymesh.com:31280",
	"uk.proxymesh.com:31280", 
	"ch.proxymesh.com:31280", 
	"us-fl.proxymesh.com:31280", 
]

print("-------------------------------------  STARTING FOR {} ----------------------------------------- ".format(isp_run.upper()))

# AT&T

if isp_run == 'att':
	proxy_choices = [
		#"us-wa.proxymesh.com:31280",
		#"fr.proxymesh.com:31280", 
		#"jp.proxymesh.com:31280", 
		"au.proxymesh.com:31280", 
		"uk.proxymesh.com:31280", 
		"nl.proxymesh.com:31280", 
		"sg.proxymesh.com:31280",
		#"us-il.proxymesh.com:31280", 
		#"us.proxymesh.com:31280", 
		#"us-dc.proxymesh.com:31280", 
		#"us-ca.proxymesh.com:31280", 
		'luminati-r',
		"us-ny.proxymesh.com:31280",
		"uk.proxymesh.com:31280", 
		"ch.proxymesh.com:31280", 
		#"us-fl.proxymesh.com:31280", 
	]

	start = datetime.now().timestamp()
	last  = start
	lock = threading.Lock()
	fatal_error_lock = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = dict()
	fatal_errors_by_proxy = dict()
	threads = list()

	for proxy in proxy_choices:
		errors_by_proxy[proxy] = 0
		fatal_errors_by_proxy[proxy] = 0

	def add_coverage_result(address, addr_id, isp, retries):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices

		is_covered = dict()
		downspeed = dict()
		upspeed = dict()

		proxy = random.choice(proxy_choices)

		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy='luminati-r')

			print_result = "(addr_id = " + str(addr_id) + ")  " + address.fullAddressWithApt() + ": "
			for code in coverage_result:
				print_result += " {}: ".format(code) + str(coverage_result[code].is_covered) + "   (" + str(coverage_result[code].down_speed) + ", " + str(coverage_result[code].up_speed) + ")"


				is_covered[code] = coverage_result[code].is_covered
				downspeed[code] = coverage_result[code].down_speed
				upspeed[code] = coverage_result[code].up_speed
			print(print_result)
		except:
			if retries < 3:
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,))
				add_coverage_thread.start()
				#if random.randint(1,10) == 2:
				#traceback.print_exc()
				#print("----HERE ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)

				#threads.append(add_coverage_thread)
				#traceback.print_exc()
			else:
				fatal_error_lock.acquire()
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				fatal_error_lock.release()

				print("ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)
				#if random.randint(1,10) == 2:
				#	traceback.print_exc()
				#print(sys.exc_info())
				traceback.print_exc()

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {}_70 = '{}', \
									{}_70 = '{}', \
									{}_70 = '{}', \
									{}_70 = '{}', \
									{}_50 = '{}', \
									{}_50 = '{}', \
									{}_50 = '{}', \
									{}_50 = '{}', \
									{}_10 = '{}', \
									{}_10 = '{}', \
									{}_10 = '{}', \
									{}_10 = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered[70], 
									'tool_coverage_downspeed_' + str(isp), downspeed[70],
									'tool_coverage_upspeed_' + str(isp), upspeed[70],
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),

									'tool_coverage_' + str(isp), is_covered[50], 
									'tool_coverage_downspeed_' + str(isp), downspeed[50],
									'tool_coverage_upspeed_' + str(isp), upspeed[50],
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									
									'tool_coverage_' + str(isp), is_covered[10], 
									'tool_coverage_downspeed_' + str(isp), downspeed[10],
									'tool_coverage_upspeed_' + str(isp), upspeed[10],
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			#mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp = isp_run
	restart_count = 0

	mycursor.execute("SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip \
						FROM addresses_{} \
						WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_50 = '1' or fcc_coverage_{}_70 = '1') and tool_coverage_att_10 in ('24','26') ORDER BY RAND() \
					".format(state, isp,isp,isp, isp)
					)

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))

	for i_row,row in enumerate(myresult):

		if i_row % 1000 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		addr_id = row[0]

		# Create the address
		address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4])
		
		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)


		if len(threads) % 100 == 1:
			print("Pausing at {} at length {}...".format(addr_id, str(len(threads))))
			time.sleep(1)
			#print("Unpausing at {}...".format(addr_id))
			#break

		
		

		if len(threads) >= 200:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=8)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current

			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 20:
			print("SLEEPING FOR TEN MINUTES")
			time.sleep(900)
			#break

			fatal_errors = 0
			threads = list()
			for proxy in proxy_choices:
				errors_by_proxy[proxy] = 0
				fatal_errors_by_proxy[proxy] = 0


			restart_count += 1
			if restart_count > 6:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				break

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join()

	lock.acquire()
	mydb.commit()
	lock.release()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()

# --------------------------------------------------------------------------------------------------

# Centurylink: 
if isp_run == 'centurylink':
	start = datetime.now().timestamp()
	last  = start
	lock = threading.Lock()
	lock_error = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = dict()
	fatal_errors_by_proxy = dict()
	threads = list()

	proxy_choices = [
				#'luminati-r',
				#"us-wa.proxymesh.com:31280",
				#"fr.proxymesh.com:31280", 
				"jp.proxymesh.com:31280", 
				"au.proxymesh.com:31280", 
				"de.proxymesh.com:31280", 
				"nl.proxymesh.com:31280", 
				"sg.proxymesh.com:31280",
				#"us-il.proxymesh.com:31280", 
				"us-dc.proxymesh.com:31280", 
				"us-ca.proxymesh.com:31280", 
				"us.proxymesh.com:31280", 
				#"us-ny.proxymesh.com:31280",
				"uk.proxymesh.com:31280", 
				"ch.proxymesh.com:31280", 
				#"us-fl.proxymesh.com:31280", 
				#'luminati-r',
				#'luminati-r',
				#'luminati-r',
				'luminati',
				'luminati',
				'luminati',
	]

	for proxy in proxy_choices:
		errors_by_proxy[proxy] = 0
		fatal_errors_by_proxy[proxy] = 0

	def add_coverage_result(address, addr_id, isp, retries):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices

		is_covered = "None"
		downspeed = '-1'
		upspeed = '-1'

		proxy = random.choice(proxy_choices)

		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy='luminati-r')
			print("(addr_id = " + str(addr_id) + ") " + address.fullAddress() + ": " + str(coverage_result.is_covered) + "   (" + str(coverage_result.down_speed) + ", " + str(coverage_result.up_speed) + ")")
			is_covered = coverage_result.is_covered
			downspeed = coverage_result.down_speed
			upspeed = coverage_result.up_speed
		except:
			if retries < 3:
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,))
				add_coverage_thread.start()
				#if random.randint(1,10) == 2:
				#	traceback.print_exc()
			else:
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				print("ERROR: " + address.fullAddress() + "   proxy: " + proxy)
				if random.randint(1,10) == 2:
					traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {} = '{}', \
									{} = '{}', \
									{} = '{}', \
									{} = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered, 
									'tool_coverage_downspeed_' + str(isp), downspeed,
									'tool_coverage_upspeed_' + str(isp), upspeed,
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp = 'centurylink'
	restart_count = 0

	if state in ['NC', 'AR']:
		mycursor.execute(f"SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip, addr_unit_type, addr_unit_id \
							FROM addresses_{state} \
							WHERE {is_known_res()} AND (fcc_coverage_{isp}_10 = '1' or fcc_coverage_{isp}_50 = '1') AND tool_coverage_{isp} = '31' ORDER BY RAND() \
						".format(state,isp,isp,isp,isp)
						)
	elif state in ['OH', 'WI']:
		mycursor.execute(f"SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip, addr_unit_type, addr_unit_id \
							FROM addresses_{state} \
							WHERE {is_known_res()} AND (fcc_coverage_{isp} = '1') AND tool_coverage_{isp} = '33' ORDER BY RAND() LIMIT 400\
						".format(state,isp,isp,isp,isp)
						)
	elif state in ['VA']:
		mycursor.execute("SELECT addr_id, addr_num, addr_street, addr_city, addr_state, addr_zip, addr_unit_type, addr_unit_id \
							FROM addresses_{} \
							WHERE (fcc_coverage_{} = '1') AND tool_coverage_{} in ('33') ORDER BY RAND() \
						".format(state,isp,isp,isp,isp)
						)

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))
	for i_row,row in enumerate(myresult):

		addr_id = row[0]

		# Create the address
		if state  == 'VA':
			address = Address(firstline=row[1] + ' ' + row[2], city=row[3], state=row[4], zipcode=row[5])
		else:
			address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4]) # REMOVED APT ID/TYPE FOR AR
		
		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)

		if len(threads) % 40 == 0:
			print("Pausing 8...")
			time.sleep(4)

		if len(threads) % 20 == 0:
			#print("Pausing...")
			time.sleep(.5)

		if i_row % 600 == 0:
			fatal_errors = 0


		if len(threads) == 100:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=8)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current


			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 30:
			fatal_errors = 0
			print("SLEEPING FOR FIFTEEN MINUTES")
			time.sleep(900)
			#break

			restart_count += 1
			if restart_count > 7:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				break

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()

# --------------------------------------------------------------------------------------------------

# Charter: 

if isp_run == 'charter':

	proxy_choices = [
		#'luminati-r',
		"us-wa.proxymesh.com:31280",
		#"fr.proxymesh.com:31280", 
		#"jp.proxymesh.com:31280", 
		#"au.proxymesh.com:31280", 
		#"de.proxymesh.com:31280", 
		#"nl.proxymesh.com:31280", 
		#"sg.proxymesh.com:31280",
		"us-il.proxymesh.com:31280", 
		"us-ny.proxymesh.com:31280",
		"us-dc.proxymesh.com:31280",
		"us.proxymesh.com:31280",
		#"uk.proxymesh.com:31280", 
		#"ch.proxymesh.com:31280", 
		"us-fl.proxymesh.com:31280", 
		"us-ca.proxymesh.com:31280", 
		#'luminati-r',
		#'luminati-r',
		'luminati-us',
		'luminati-us',
		'luminati-us',
		'luminati-us',
		'luminati-us',
		'luminati-us',
	]
	start = datetime.now().timestamp()
	last  = start
	fatal_error_lock = threading.Lock()
	lock = threading.Lock()
	lock_error = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = defaultdict(lambda: 0)
	fatal_errors_by_proxy = defaultdict(lambda:0)
	error_count = 0
	threads = list()

	def add_coverage_result(address, addr_id, isp, retries,user_agent=None):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices
		global error_count

		is_covered = dict()
		downspeed = dict()
		upspeed = dict()

		if user_agent==None:
			user_agent = random.choice(user_agents_ipad)
		proxy = user_agent

		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy='luminati-r',data=user_agent)

			is_covered = coverage_result.is_covered
			downspeed = coverage_result.down_speed
			upspeed = coverage_result.up_speed
			print("(addr_id = " + str(addr_id) + ") " + address.fullAddressWithApt() + ": " + str(coverage_result.is_covered) + "   (" + str(coverage_result.down_speed) + ", " + str(coverage_result.up_speed) + ")")
		except:
			if retries < 3:
				fatal_error_lock.acquire()
				error_count += 1
				#errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,user_agent))
				add_coverage_thread.start()
				fatal_error_lock.release()
				#traceback.print_exc()
			else:
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				print("ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)
				if random.randint(1,10) == 2:
					traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {} = '{}', \
									{} = '{}', \
									{} = '{}', \
									{} = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered, 
									'tool_coverage_downspeed_' + str(isp), downspeed,
									'tool_coverage_upspeed_' + str(isp), upspeed,
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			#mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp = 'charter'
	restart_count = 0
	# NEED TO RERUN THE CALLS TO VERIFY (24)
	mycursor.execute("SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip, addr_unit_type, addr_unit_id \
						FROM addresses_{} \
						WHERE fcc_coverage_{} = '1' and tool_coverage_{} = '23' LIMIT 400 \
					".format(state, isp,isp,isp, isp)
					)

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))
	for i_row,row in enumerate(myresult):

		#print(row)
		addr_id = row[0]

		# Create the address
		address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4], apt_type=row[5], apt_number=row[6])

		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)

		if i_row % 400 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		if len(threads) % 50 == 0 and len(threads) != 0:
			print("Pausing 5 at {}...".format(addr_id))
			time.sleep(1.8)
			#print("Unpausing at {}...".format(addr_id))
			#break

		
		

		if len(threads) > 50:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=3)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current

			print(f'Error count: {error_count}')
			#pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 30:
			print("SLEEPING FOR 45 SECONDS")
			time.sleep(45)
			#break

			fatal_errors = 0
			threads = list()
			for proxy in proxy_choices:
				errors_by_proxy[proxy] = 0
				fatal_errors_by_proxy[proxy] = 0


			restart_count += 1
			if restart_count > 60:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				break

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join()

	lock.acquire()
	#mydb.commit()
	lock.release()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()

# --------------------------------------------------------------------------------------------------

# Consolidated: 

if isp_run == 'consolidated':
	start = datetime.now().timestamp()
	last  = start
	lock = threading.Lock()
	lock_error = threading.Lock()
	fatal_error_lock = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = dict()
	fatal_errors_by_proxy = dict()
	threads = list()

	for proxy in proxy_choices:
		errors_by_proxy[proxy] = 0
		fatal_errors_by_proxy[proxy] = 0

	def add_coverage_result(address, addr_id, isp, retries):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices

		is_covered = dict()
		downspeed = dict()
		upspeed = dict()

		proxy = random.choice(proxy_choices)

		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy='luminati-us')

			is_covered = coverage_result.is_covered
			downspeed = coverage_result.down_speed
			upspeed = coverage_result.up_speed
			print("(addr_id = " + str(addr_id) + ") " + address.fullAddressWithApt() + ": " + str(coverage_result.is_covered) + "   (" + str(coverage_result.down_speed) + ", " + str(coverage_result.up_speed) + ")")
		except:
			if retries < 3:
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,))
				add_coverage_thread.start()
				threads.append(add_coverage_thread)
				#traceback.print_exc()
			else:
				fatal_error_lock.acquire()
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				print("ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)
				fatal_error_lock.release()
				if random.randint(1,10) == 2:
					traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {} = '{}', \
									{} = '{}', \
									{} = '{}', \
									{} = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered, 
									'tool_coverage_downspeed_' + str(isp), downspeed,
									'tool_coverage_upspeed_' + str(isp), upspeed,
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp = isp_run
	restart_count = 0

	mycursor.execute("SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip \
						FROM addresses_{} \
						WHERE fcc_coverage_{} = '1' and tool_coverage_{} is null ORDER BY RAND() \
					".format(state, isp,isp,isp, isp)
					)

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))
	for i_row,row in enumerate(myresult):

		#print(row)
		addr_id = row[0]

		if i_row % 700 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		# Create the address
		address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4])
		
		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)

		if len(threads) % 10 == 1:
			time.sleep(2)

		if len(threads) > 30:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=8)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current

			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))
			time.sleep(3)

		if fatal_errors > 30:
			print("SLEEPING FOR TEN MINUTES")
			time.sleep(900)
			#break

			fatal_errors = 0
			threads = list()
			for proxy in proxy_choices:
				errors_by_proxy[proxy] = 0
				fatal_errors_by_proxy[proxy] = 0


			restart_count += 1
			if restart_count > 6:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				break

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join()

	lock.acquire()
	#mydb.commit()
	lock.release()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()

# --------------------------------------------------------------------------------------------------

# COX: 

if isp_run == 'cox':

	proxy_choices = [
		#"us-wa.proxymesh.com:31280",
		#"fr.proxymesh.com:31280", 
		"jp.proxymesh.com:31280", 
		"au.proxymesh.com:31280", 
		"uk.proxymesh.com:31280", 
		"nl.proxymesh.com:31280", 
		"sg.proxymesh.com:31280",
		#"us-il.proxymesh.com:31280", 
		"us.proxymesh.com:31280", 
		"us-dc.proxymesh.com:31280", 
		"us-ca.proxymesh.com:31280", 
		#"us-ny.proxymesh.com:31280",
		"uk.proxymesh.com:31280", 
		"ch.proxymesh.com:31280", 
		#"us-fl.proxymesh.com:31280", 
		#'luminati-r'
	]
	start = datetime.now().timestamp()
	last  = start
	lock = threading.Lock()
	lock_error = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = dict()
	fatal_errors_by_proxy = dict()
	threads = list()
	fatal_error_lock = threading.Lock()

	for proxy in proxy_choices:
		errors_by_proxy[proxy] = 0
		fatal_errors_by_proxy[proxy] = 0

	def add_coverage_result(address, addr_id, isp, retries):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices

		is_covered = "None"
		downspeed = '-1'
		upspeed = '-1'

		proxy = random.choice(proxy_choices)

		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy=proxy)
			print("(addr_id = " + str(addr_id) + ") " + address.fullAddressWithApt() + ": " + str(coverage_result.is_covered) + "   (" + str(coverage_result.down_speed) + ", " + str(coverage_result.up_speed) + ")")
			is_covered = coverage_result.is_covered
			downspeed = coverage_result.down_speed
			upspeed = coverage_result.up_speed
		except:
			if retries < 3:
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,))
				add_coverage_thread.start()
				#threads.append(add_coverage_thread)
				#traceback.print_exc()
			else:
				fatal_error_lock.acquire()
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				fatal_error_lock.release()

				print("ERROR: " + address.fullAddress() + "   proxy: " + proxy)
				#traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {} = '{}', \
									{} = '{}', \
									{} = '{}', \
									{} = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered, 
									'tool_coverage_downspeed_' + str(isp), downspeed,
									'tool_coverage_upspeed_' + str(isp), upspeed,
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp_short_sql = 'cox'
	isp = 'cox'
	retries = 0

	
	if state == 'AR':
		mycursor.execute("SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip \
							FROM addresses_{} \
							WHERE fcc_coverage_{} = '1' and tool_coverage_{} in ('31', '37') ORDER BY rand()\
						".format(state,isp,isp,isp,isp)
						)
	else:
		mycursor.execute("SELECT addr_id, addr_num, addr_street, addr_city, addr_state, addr_zip \
						FROM addresses_{} \
						WHERE fcc_coverage_{} = '1' and tool_coverage_{} in ('33', '37', '7') ORDER BY rand()\
					".format(state,isp,isp,isp,isp)
					)

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))

	for i_row,row in enumerate(myresult):

		if i_row % 700 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		addr_id = row[0]

		# Create the address
		if state == 'AR':
			address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4], apt_number=row[5])
		else:
			address = Address(firstline=row[1] + ' ' + row[2], city=row[3], state=row[4], zipcode=row[5])
		
		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)

		if len(threads) % 20 == 0:
			print("Pausing 6 at {}...".format(addr_id))
			time.sleep(4)
			print("Unpausing at {}...".format(addr_id))

		if len(threads) % 10 == 0:
			#print("Pausing...")
			time.sleep(1)

		if len(threads) >= 89:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=8)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current


			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("Sleeping...")
			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 25:
			if retries < 8:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				#exit()
				retries += 1
				time.sleep(900)
				fatal_error_lock.acquire()
				fatal_errors = 0
				fatal_error_lock.release()
			else:
				exit()

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join()

	lock.acquire()
	mydb.commit()
	lock.release()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()


# --------------------------------------------------------------------------------------------------


# XFINITY: 
if isp_run == 'xfinity':

	proxy_choices = [
		#"us-wa.proxymesh.com:31280",
		#"fr.proxymesh.com:31280", 
		"jp.proxymesh.com:31280", 
		"au.proxymesh.com:31280", 
		"uk.proxymesh.com:31280", 
		"nl.proxymesh.com:31280", 
		"sg.proxymesh.com:31280",
		#"us-il.proxymesh.com:31280", 
		#"us.proxymesh.com:31280", 
		#"us-dc.proxymesh.com:31280", 
		#"us-ca.proxymesh.com:31280", 
		"us-ny.proxymesh.com:31280",
		"uk.proxymesh.com:31280", 
		"ch.proxymesh.com:31280", 
		#"us-fl.proxymesh.com:31280", 
		'luminati-us',
		'luminati-us',
		'luminati-us',
		#'luminati-r',
		#'luminati-r',
	]

	start = datetime.now().timestamp()
	last  = start
	lock = threading.Lock()
	lock_error = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = dict()
	fatal_errors_by_proxy = dict()
	threads = list()
	fatal_error_lock = threading.Lock()

	for proxy in proxy_choices:
		errors_by_proxy[proxy] = 0
		fatal_errors_by_proxy[proxy] = 0

	def add_coverage_result(address, addr_id, isp, retries):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices

		is_covered = "None"
		downspeed = '-1'
		upspeed = '-1'

		proxy = random.choice(proxy_choices)
		#proxy='luminati-us'
		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy=proxy)
			print("(addr_id = " + str(addr_id) + ") " + address.fullAddressWithApt() + ": " + str(coverage_result.is_covered) + "   (" + str(coverage_result.down_speed) + ", " + str(coverage_result.up_speed) + ")")
			is_covered = coverage_result.is_covered
			downspeed = coverage_result.down_speed
			upspeed = coverage_result.up_speed
		except:
			if retries < 3:
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,))
				add_coverage_thread.start()
				'''
				threads.append(add_coverage_thread)
				if random.randint(1,10) == 2:
					traceback.print_exc()
					print("----ERROR: " + address.fullAddress() + "   proxy: " + proxy)
				'''
				#traceback.print_exc()
			else:
				fatal_error_lock.acquire()
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				fatal_error_lock.release()

				print("ERROR: " + address.fullAddress() + "   proxy: " + proxy)
				if random.randint(1,10) == 2:
					traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {} = '{}', \
									{} = '{}', \
									{} = '{}', \
									{} = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered, 
									'tool_coverage_downspeed_' + str(isp), downspeed,
									'tool_coverage_upspeed_' + str(isp), upspeed,
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp_short_sql = 'xfinity'
	isp = 'xfinity'
	retries = 0

	'''
	mycursor.execute("SELECT addr_id, addr_num, addr_street, addr_city, addr_state, addr_zip, addr_unit_type, addr_unit_id \
						FROM (SELECT * FROM addresses_{} WHERE fcc_coverage_{} = '1' ORDER BY RAND(5) LIMIT 6000)a \
						WHERE fcc_coverage_{} = '1' and tool_coverage_{} in ('0') \
					".format(state,isp,isp,isp)
					)
	'''
	mycursor.execute("SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip, addr_unit_type, addr_unit_id \
						FROM addresses_{} \
						WHERE fcc_coverage_{} = '1' and tool_coverage_{} = '' ORDER BY RAND() \
					".format(state,isp,isp,isp)
					)
	

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))

	for i_row,row in enumerate(myresult):

		if i_row % 700 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		addr_id = row[0]

		# Create the address
		#address = Address(firstline=row[1] + ' ' + row[2], city=row[3], state=row[4], zipcode=row[5], apt_type=row[6], apt_number=row[7])
		address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4])
		
		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)


		if len(threads) % 100 == 0:
			#print("Pausing...")
			time.sleep(2)

		if len(threads) >= 249:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=8)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current


			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("Sleeping...")
			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 10:
			if retries < 8:
				
				#exit()
				print("--------------------------SLEEPING" + str(fatal_errors) + "------------------------")
				retries += 1
				time.sleep(400)
				fatal_error_lock.acquire()
				fatal_errors = 0
				fatal_error_lock.release()
			else:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				exit()

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join()

	lock.acquire()
	mydb.commit()
	lock.release()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()


# --------------------------------------------------------------------------------------------------

# Verizon: 

if isp_run == 'verizon':

	proxy_choices = [
		'luminati-r',
		'luminati-r',
		'luminati-r',
		'luminati-r',
		'luminati-r',
		'luminati-r',
		'luminati-r',
		'luminati-r',
		'luminati-r',
		#'luminati-us',
		#'luminati-us',
		#'luminati-us',
		#'luminati-us',
	]

	start = datetime.now().timestamp()
	last  = start
	lock = threading.Lock()
	fatal_error_lock = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = dict()
	fatal_errors_by_proxy = dict()
	threads = list()

	#proxy_choices = ['luminati-r', 'luminati-us']

	for proxy in proxy_choices:
		errors_by_proxy[proxy] = 0
		fatal_errors_by_proxy[proxy] = 0

	def add_coverage_result(address, addr_id, isp, retries):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices

		is_covered = dict()
		downspeed = dict()
		upspeed = dict()

		try:
			choice = random.random()
			#print(choice)
			if choice > .1:
				proxy = 'luminati-r'
			else:
				proxy = 'luminati-us'

			proxy = random.choice(proxy_choices)
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy='luminati')
			if coverage_result == 100:
				print('Mismatch!')
				return
			#coverage_result_check =tool.make_request(isp=isp, address=address, debug=False, proxy='luminati-r')

			'''
			if (coverage_result[10].is_covered != coverage_result_check[10].is_covered) or (coverage_result[50].is_covered != coverage_result_check[50].is_covered):
				print(f'Inconsitency at addr_id: {addr_id}, addr:{address.fullAddress()}')
				pp.pprint(coverage_result)
				pp.pprint(coverage_result_check)
				return
			'''
			print_result = "(addr_id = " + str(addr_id) + ")  " + address.fullAddress() + ": "
			for code in coverage_result:
				print_result += " {}: ".format(code) + str(coverage_result[code].is_covered) + "   (" + str(coverage_result[code].down_speed) + ", " + str(coverage_result[code].up_speed) #+ ")    Proxy: {}".format(proxy)


				is_covered[code] = coverage_result[code].is_covered
				downspeed[code] = coverage_result[code].down_speed
				upspeed[code] = coverage_result[code].up_speed
			print(print_result)
		except:
			if retries < 3:
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,))
				add_coverage_thread.start()
				if retries == 0:
					threads.append(add_coverage_thread)
				#print("----HERE ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)

				#threads.append(add_coverage_thread)
				#traceback.print_exc()
			else:
				fatal_error_lock.acquire()
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				fatal_error_lock.release()

				print("ERROR: " + address.fullAddress() + "   proxy: " + proxy)
				if random.randint(1,10) == 2:
					traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {}_50 = '{}', \
									{}_50 = '{}', \
									{}_50 = '{}', \
									{}_50 = '{}', \
									{}_10 = '{}', \
									{}_10 = '{}', \
									{}_10 = '{}', \
									{}_10 = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered[50], 
									'tool_coverage_downspeed_' + str(isp), downspeed[50],
									'tool_coverage_upspeed_' + str(isp), upspeed[50],
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									'tool_coverage_' + str(isp), is_covered[10], 
									'tool_coverage_downspeed_' + str(isp), downspeed[10],
									'tool_coverage_upspeed_' + str(isp), upspeed[10],
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			#mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp = 'verizon'
	restart_count = 0
	
	
	if state == 'VA':
		mycursor.execute("SELECT addr_id, addr_num, addr_street, addr_city, addr_state, addr_zip \
							FROM addresses_{}\
							WHERE (fcc_coverage_verizon_10 = '0' and fcc_coverage_verizon_50 = '0') ORDER BY RAND() \
						".format(state, isp,isp, isp, isp)
						)
	elif state in ['MA', 'NY']:
		mycursor.execute(f"SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip \
							FROM addresses_{state}  \
							WHERE {is_known_res()} AND (fcc_coverage_verizon_10 = '1' or fcc_coverage_verizon_50 = '1') and (tool_coverage_verizon_10 = '30') ORDER BY RAND()"
						)
	
	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))

	for i_row,row in enumerate(myresult):

		if i_row % 600 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		addr_id = row[0]

		# Create the address
		if state in ['MA', 'NY']:
			address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4])
		elif state == 'VA':
			address = Address(firstline=row[1] + ' ' + row[2], city=row[3], state=row[4], zipcode=row[5])
		
		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)

		if len(threads) % 25 == 0 and len(threads) != 0:
			print("Pausing at {} at length {}...".format(addr_id, str(len(threads))))
			time.sleep(2)

		if len(threads) % 10 == 0 and len(threads) != 0:
			print("Pausing at {} at length {}...".format(addr_id, str(len(threads))))
			time.sleep(.2)
			#print("Unpausing at {}...".format(addr_id))
			#break
		

		if len(threads) >= 49:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=3)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current

			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 30:
			print("SLEEPING FOR TEN MINUTES")
			time.sleep(300)
			#break

			fatal_errors = 0
			threads = list()
			for proxy in proxy_choices:
				errors_by_proxy[proxy] = 0
				fatal_errors_by_proxy[proxy] = 0


			restart_count += 1
			if restart_count > 10:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				break

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join()

	lock.acquire()
	mydb.commit()
	lock.release()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()

# --------------------------------------------------------------------------------------------------

# Windstream: 

if isp_run == 'windstream':
	start = datetime.now().timestamp()
	last  = start
	lock = threading.Lock()
	lock_error = threading.Lock()
	fatal_error_lock = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = dict()
	fatal_errors_by_proxy = dict()
	threads = list()

	for proxy in proxy_choices:
		errors_by_proxy[proxy] = 0
		fatal_errors_by_proxy[proxy] = 0

	def add_coverage_result(address, addr_id, isp, retries):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices

		is_covered = dict()
		downspeed = dict()
		upspeed = dict()

		proxy = random.choice(proxy_choices)

		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy='luminati')

			is_covered = coverage_result.is_covered
			downspeed = coverage_result.down_speed
			upspeed = coverage_result.up_speed
			print("(addr_id = " + str(addr_id) + ") " + address.fullAddress() + ": " + str(coverage_result.is_covered) + "   (" + str(coverage_result.down_speed) + ", " + str(coverage_result.up_speed) + ")")
		except:
			if retries < 3:
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,))
				add_coverage_thread.start()
				threads.append(add_coverage_thread)
				#traceback.print_exc()
			else:
				fatal_error_lock.acquire()
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				print("ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)
				fatal_error_lock.release()
				if random.randint(1,10) == 2:
					traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {} = '{}', \
									{} = '{}', \
									{} = '{}', \
									{} = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered, 
									'tool_coverage_downspeed_' + str(isp), downspeed,
									'tool_coverage_upspeed_' + str(isp), upspeed,
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp = isp_run
	restart_count = 0

	'''
	mycursor.execute("SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip, addr_unit_id \
						FROM addresses_{} \
						WHERE fcc_coverage_{} = '1' and tool_coverage_{} is null \
					".format(state, isp,isp,isp, isp)
					)
				'''
	if state == 'OH':
		mycursor.execute("SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip, addr_unit_id \
								FROM addresses_{} \
								WHERE fcc_coverage_{} and tool_coverage_{} = '100' \
							".format(state, isp,isp,isp, isp)
							)
	else:
		mycursor.execute("SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip, addr_unit_id \
								FROM addresses_{} \
								WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_41 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} is null ORDER BY rand() \
							".format(state, isp,isp,isp, isp)
							)

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))
	for i_row,row in enumerate(myresult):

		addr_id = row[0]

		if i_row % 700 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		# Create the address
		address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4], apt_number=row[5])
		
		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)

		if len(threads) % 30 == 1:
			time.sleep(2)

		if len(threads) > 349:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=8)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current

			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 30:
			print("SLEEPING FOR TEN MINUTES")
			time.sleep(900)
			#break

			fatal_errors = 0
			threads = list()
			for proxy in proxy_choices:
				errors_by_proxy[proxy] = 0
				fatal_errors_by_proxy[proxy] = 0


			restart_count += 1
			if restart_count > 6:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				break

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()


# --------------------------------------------------------------------------------------------------

# Charter: 

if isp_run == 'altice':
	proxy_choices = [
				#'luminati-r',
				"us-wa.proxymesh.com:31280",
				#"fr.proxymesh.com:31280", 
				#"jp.proxymesh.com:31280", 
				#"au.proxymesh.com:31280", 
				#"de.proxymesh.com:31280", 
				#"nl.proxymesh.com:31280", 
				#"sg.proxymesh.com:31280",
				#"us-il.proxymesh.com:31280", 
				"us-ny.proxymesh.com:31280",
				"us-dc.proxymesh.com:31280",
				#"us.proxymesh.com:31280",
				#"uk.proxymesh.com:31280", 
				#"ch.proxymesh.com:31280", 
				#"us.proxymesh.com:31280", 
				"us-fl.proxymesh.com:31280", 
				"us-ca.proxymesh.com:31280", 
				#'luminati-r',
				#'luminati-r',
				#'luminati-r',
				#'luminati-r',
				#'luminati-r',
				'luminati-r',
				'luminati-us',
				#'luminati-us',
				#'luminati-us',
				#'luminati-us',
				#'luminati-us',
	]

	start = datetime.now().timestamp()
	last  = start
	fatal_error_lock = threading.Lock()
	lock = threading.Lock()
	lock_error = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = defaultdict(lambda: 0)
	fatal_errors_by_proxy = defaultdict(lambda:0)
	error_count = 0
	threads = list()

	def add_coverage_result(address, addr_id, isp, retries,user_agent=None):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices
		global error_count

		is_covered = dict()
		downspeed = dict()
		upspeed = dict()

		proxy = random.choice(proxy_choices)

		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy=proxy)

			is_covered = coverage_result.is_covered
			downspeed = coverage_result.down_speed
			upspeed = coverage_result.up_speed
			print("(addr_id = " + str(addr_id) + ") " + address.fullAddressWithApt() + ": " + str(coverage_result.is_covered) + "   (" + str(coverage_result.down_speed) + ", " + str(coverage_result.up_speed) + ")")
		except:
			if retries < 3:
				fatal_error_lock.acquire()
				error_count += 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_error_lock.release()
				print("ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)
				if random.randint(1,10) == 2:
					traceback.print_exc()
				return
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,user_agent))
				add_coverage_thread.start()
				fatal_error_lock.release()
				#traceback.print_exc()
				if retries == 0:
					threads.append(add_coverage_thread)
			else:
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				print("ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)
				if random.randint(1,10) == 2:
					traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {} = '{}', \
									{} = '{}', \
									{} = '{}', \
									{} = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered, 
									'tool_coverage_downspeed_' + str(isp), downspeed,
									'tool_coverage_upspeed_' + str(isp), upspeed,
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp = 'altice'
	restart_count = 0
	mycursor.execute(f"SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip \
						FROM addresses_{state} \
						WHERE fcc_coverage_{isp} = '1' and tool_coverage_{isp} is null and {is_known_res()} ORDER BY RAND() \
					"
					)
	# and addr_id < 3000000

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))

	for i_row,row in enumerate(myresult):

		#print(row)
		addr_id = row[0]

		# Create the address
		address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4])
		print(address.fullAddress())

		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)

		if i_row % 700 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		if len(threads) % 41 == 0 and len(threads) != 0:
			print("Pausing 5 at {}...".format(addr_id))
			time.sleep(1)

		
		

		if len(threads) > 5:
			print(addr_id)
			print("Waiting for threads...")
			#time.sleep(30)
			print('done waiting')
			for i, thread in enumerate(threads):
				thread.join(timeout=5)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current

			print(f'Error count: {error_count}')
			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 20:
			print("SLEEPING FOR 45 SECONDS")
			time.sleep(2300)
			#break

			fatal_errors = 0
			threads = list()
			for proxy in proxy_choices:
				errors_by_proxy[proxy] = 0
				fatal_errors_by_proxy[proxy] = 0


			restart_count += 1
			if restart_count > 17:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				break

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join(timeout=2)

	lock.acquire()
	#mydb.commit()
	lock.release()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()

# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------

# Charter: 

if isp_run == 'frontier':
	proxy_choices = [
				#'luminati-r',
				#"us-wa.proxymesh.com:31280",
				#"fr.proxymesh.com:31280", 
				#"jp.proxymesh.com:31280", 
				#"au.proxymesh.com:31280", 
				#"de.proxymesh.com:31280", 
				#"nl.proxymesh.com:31280", 
				#"sg.proxymesh.com:31280",
				#"us-il.proxymesh.com:31280", 
				"us-dc.proxymesh.com:31280", 
				"us-ca.proxymesh.com:31280", 
				"us.proxymesh.com:31280", 
				#"us-ny.proxymesh.com:31280",
				#"uk.proxymesh.com:31280", 
				#"ch.proxymesh.com:31280", 
				#"us-fl.proxymesh.com:31280", 
				#'luminati-r',
				#'luminati-r',
				#'luminati-r',
				'luminati-us',
				'luminati-us',
				'luminati-r',
				'luminati-us',
				'luminati-r',
				'luminati-r',
				'luminati-r',
				'luminati-r',
				'luminati-r',
				'luminati-r',
	]

	start = datetime.now().timestamp()
	last  = start
	fatal_error_lock = threading.Lock()
	lock = threading.Lock()
	lock_error = threading.Lock()
	fatal_errors = 0
	errors_by_proxy = defaultdict(lambda: 0)
	fatal_errors_by_proxy = defaultdict(lambda:0)
	error_count = 0
	threads = list()

	def add_coverage_result(address, addr_id, isp, retries,user_agent=None):

		tool = IspApiTool()
		global fatal_errors
		global errors_by_proxy
		global fatal_errors_by_proxy
		global lock
		global proxy_choices
		global error_count

		is_covered = dict()
		downspeed = dict()
		upspeed = dict()

		if user_agent==None:
			user_agent = random.choice(user_agents_ipad)
		proxy = random.choice(proxy_choices)

		try:
			coverage_result =tool.make_request(isp=isp, address=address, debug=False, proxy=proxy)

			is_covered = coverage_result.is_covered
			downspeed = coverage_result.down_speed
			upspeed = coverage_result.up_speed
			print("(addr_id = " + str(addr_id) + ") " + address.fullAddressWithApt() + ": " + str(coverage_result.is_covered) + "   (" + str(coverage_result.down_speed) + ", " + str(coverage_result.up_speed) + ")")
		except:
			if retries < 3:
				fatal_error_lock.acquire()
				error_count += 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, retries+1,user_agent))
				add_coverage_thread.start()
				fatal_error_lock.release()
				#traceback.print_exc()
			else:
				fatal_errors = fatal_errors + 1
				errors_by_proxy[proxy] = errors_by_proxy[proxy] + 1 
				fatal_errors_by_proxy[proxy] = fatal_errors_by_proxy[proxy] + 1
				print("ERROR: " + address.fullAddressWithApt() + "   proxy: " + proxy)
				if random.randint(1,10) == 2:
					traceback.print_exc()
				#print(sys.exc_info())

			return
		lock.acquire()
		try:
			mycursor.execute("UPDATE addresses_{} \
								SET {} = '{}', \
									{} = '{}', \
									{} = '{}', \
									{} = '{}' \
								WHERE addr_id = {} \
								".format(
									state,
									'tool_coverage_' + str(isp), is_covered, 
									'tool_coverage_downspeed_' + str(isp), downspeed,
									'tool_coverage_upspeed_' + str(isp), upspeed,
									'tool_timestamp_' + str(isp), datetime.now().timestamp(),
									addr_id
								)
							)
			mydb.commit()
		except:
			print("----Execute failure at addr_id={}!".format(addr_id))
			traceback.print_exc()
			pass
		lock.release()

	# --------

	isp = 'frontier'
	restart_count = 0
	mycursor.execute(f"SELECT addr_id, addr_line1, addr_city, addr_state, addr_zip \
						FROM addresses_{state} \
						WHERE fcc_coverage_{isp} = '0' and tool_coverage_{isp} is null and {is_known_res()} order by rand() LIMIT 3\
					"
					)

	myresult = mycursor.fetchall()
	myresult = myresult.copy()

	print("Count: " + str(len(myresult)))
	for i_row,row in enumerate(myresult):

		#print(row)
		addr_id = row[0]

		# Create the address
		address = Address(firstline=row[1], city=row[2], state=row[3], zipcode=row[4])

		add_coverage_thread = threading.Thread(target=add_coverage_result, args=(address, addr_id, isp, 0))
		add_coverage_thread.start()
		threads.append(add_coverage_thread)

		if i_row % 700 == 0:
			fatal_error_lock.acquire()
			fatal_errors = 0
			fatal_error_lock.release()

		if len(threads) % 41 == 0 and len(threads) != 0:
			print("Pausing 5 at {}...".format(addr_id))
			time.sleep(1)
			#print("Unpausing at
		if len(threads) % 21 == 0 and len(threads) != 0:
			print("Pausing 5 at {}...".format(addr_id))
			time.sleep(.4)
			#print("Unpausing at

		if len(threads) % 10 == 0 and len(threads) != 0:
			print("Pausing 5 at {}...".format(addr_id))
			time.sleep(.2)
			#print("Unpausing at {}...".format(addr_id))
			#break

		
		

		if len(threads) > 60:
			print(addr_id)
			print("Waiting for threads...")
			for i, thread in enumerate(threads):
				thread.join(timeout=1)
			print("Finished waiting for threads...")
			threads = list()

			print("Fatal Error count: " + str(fatal_errors))

			current = datetime.now().timestamp()
			print("Time (this cycle): " + str(current-last))
			print("Time (total): " + str(current-start))
			last = current

			print(f'Error count: {error_count}')
			pp.pprint(errors_by_proxy)
			pp.pprint(fatal_errors_by_proxy)

			print("-------------------------------------  GETTING NEXT SET (i={}) ----------------------------------------- ".format(str(i_row)))

		if fatal_errors > 20:
			print("SLEEPING FOR 45 SECONDS")
			time.sleep(2300)
			#break

			fatal_errors = 0
			threads = list()
			for proxy in proxy_choices:
				errors_by_proxy[proxy] = 0
				fatal_errors_by_proxy[proxy] = 0


			restart_count += 1
			if restart_count > 17:
				print("--------------------------ENDING EARLY: Fatal Error count: " + str(fatal_errors) + "------------------------")
				break

	print("Waiting for final threads...")
	for i, thread in enumerate(threads):
		thread.join(timeout=2)

	lock.acquire()
	#mydb.commit()
	lock.release()

	end = datetime.now().timestamp()
	print("Time: " + str(end-start))
	print("Fatal Error count: " + str(fatal_errors))
	pp.pprint(errors_by_proxy)
	pp.pprint(fatal_errors_by_proxy)

	exit()

# --------------------------------------------------------------------------------------------------