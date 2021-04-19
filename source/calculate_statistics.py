import csv
from collections import defaultdict
import shapefile
import sqlparse
import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
import pprint
import sys
import pandas as pd
from response_breakdowns import ISP_FULL_NAMES, UNKNOWN_RESPONSES, ALL_ISPS, ALL_RESPONSES, POS_RESPONSES, NEG_RESPONSES, UNRECOGNIZED_RESPONSES, BUSINESS_RESPONSES, EXCLUDED_RESPONSES, ISPS_PER_STATE, STATES, LABELS, STATES_TUPLE
import matplotlib.pyplot as plt
import seaborn as sns
import random

pp = pprint.PrettyPrinter(indent=4)
NULL = '-123'

def is_known_res():
	sql_statement = "(addr_dpv in ('Y','D','S') and addr_rdi = 'R')"
	return sql_statement

action = sys.argv[1]


def main():
	# Get coverage for each isp
	if action == 'coverage_isp':
		coverage_isp()
	# IN PAPER: Get coverage for each isp, broken down by urban/rural and speeds
	elif action == 'coverage_isp_rural':
		coverage_isp_rural()
	# IN PAPER: total coverage, broken down by urban/rural and speeds
	elif action == 'total_coverage_rural':
		total_coverage_rural()
	# gets total coverage for every state
	elif action == 'latex_total_coverage_pop_tool_real':
		latex_total_coverage_pop_tool_real()
	# IN PAPER: Gets number of empty blocks across all ISPs
	elif action == 'empty_blocks_total':
		empty_blocks_total()
	# USED FOR PAPER: get counts of excluded blocks
	elif action == 'get_excluded_blocks':
		get_excluded_blocks()
	# Gets local coverage %s
	elif action == 'local_coverage':
		local_coverage()
	elif action == 'major_coverage':
		major_coverage()
	elif action == 'pop_per_state':
		pop_per_state()
	elif action == 'now':
		now()
	elif action == 'get_isps_per_block':
		for state in STATES:
			get_isps_per_block(state, 25)
	elif action == 'a':
		a()
	else: 
		pass

def now():

	if True:
		state = 'VT'
		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  #database='{}_addresses'.format(state),
		)
		mycursor = mydb.cursor(buffered=True)
		mycursor.execute(f"{state}_addresses.dump")

	if False:
		responses_per_isp = defaultdict(lambda: (defaultdict(lambda:0)))
		for state in STATES:
			print(state)
			mydb = mysql.connector.connect(
			  host="localhost",
			  user="root",
			  passwd="",
			  database='{}_addresses'.format(state),
			)


			# Create cursor
			mycursor = mydb.cursor(buffered=True)
			for isp in ISPS_PER_STATE[state]:
				if isp in ('verizon'):
					continue
				if isp == 'att':
					mycursor.execute(f"SELECT tool_coverage_{isp}_10, count(*) FROM  addresses_{state} WHERE {is_known_res()} GROUP BY tool_coverage_{isp}_10")
				else:
					mycursor.execute(f"SELECT tool_coverage_{isp}, count(*) FROM  addresses_{state} WHERE {is_known_res()} GROUP BY tool_coverage_{isp}")
				myresult = mycursor.fetchall()
				for i, row in enumerate(myresult):
					responses_per_isp[isp][row[0]] += int(row[1])

		pp.pprint(responses_per_isp)
	if False:
		for state in STATES:
			print(state)
			mydb = mysql.connector.connect(
			  host="localhost",
			  user="root",
			  passwd="",
			  database='{}_addresses'.format(state),
			)


			# Create cursor
			mycursor = mydb.cursor(buffered=True)
			mycursor.execute(f"SELECT addr_id, addr_full, addr_state FROM  addresses_{state} WHERE addr_state not in {STATES_TUPLE}")
			myresult = mycursor.fetchall()
			for i, row in enumerate(myresult):
				print(row)
		exit()

def fcc_covers(isp,speed):
	return f"(fcc_coverage_{isp} = '1' AND fcc_coverage_downspeed_{isp} >= {speed})"

def tool_select_fields(state):
	statement = ''
	for i,isp in enumerate(ISPS_PER_STATE[state]):
		if i != 0:
			statement += ', '
		if isp == 'verizon':
			statement += 'tool_coverage_verizon_10, tool_coverage_verizon_50'
		elif isp == 'att':
			statement += 'tool_coverage_att_10, tool_coverage_att_50, tool_coverage_att_70'
		else:
			statement += f'tool_coverage_{isp}'
	return statement

def fcc_select_fields(state):
	statement = ''
	for i,isp in enumerate(ISPS_PER_STATE[state]):
		if i != 0:
			statement += ', '
		if isp == 'verizon':
			statement += 'fcc_coverage_verizon_10, fcc_coverage_verizon_50'
		elif isp == 'att':
			statement += 'fcc_coverage_att_10, fcc_coverage_att_50, fcc_coverage_att_70'
		elif state in ['AR','NC'] and isp == 'centurylink':
			statement += 'fcc_coverage_centurylink_10, fcc_coverage_centurylink_50'
		elif isp == 'windstream' and state == 'NC':
			statement += 'fcc_coverage_windstream_10, fcc_coverage_windstream_41, fcc_coverage_windstream_50'
		else:
			statement += f'fcc_coverage_{isp}'
	return statement



def sql_print(sql_statement):
	print(sqlparse.format(sql_statement, reindent=True, keyword_case='upper', wrap_after=100))

def get_census_block_population_counts(state, mycursor):
	### Get census block population estimates
	data = pd.read_csv('PopulationCounts/{}CensusBlockPopCounts.csv'.format(state), header=0, sep=',', lineterminator='\n')

	blocks_pop = dict()

	for i, row in data.iterrows():
		if row['block_fips'] in blocks_pop:
			raise Exception()
		blocks_pop[str(row['block_fips'])] = int(row['pop2018'])
	return blocks_pop

'''
	The total count of units covered according to FCC data
'''
def fcc_covered_sql(state, limit_to_tool_blocks, speed, method):
	sql_statement = "( "

	sql_statement += "( "
	# FCC coverage is positive and >= speed for at least one 
	for i, isp in enumerate(ISPS_PER_STATE[state]):
		if i != 0:
			sql_statement += "OR "
		if isp == 'verizon' or (isp == 'centurylink' and state in ['AR','NC']):
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_50 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed})) "
		elif isp == 'att':
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_50 = '1' OR fcc_coverage_{isp}_70 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed} OR fcc_coverage_downspeed_{isp}_70 >= {speed} )) "
		elif isp == 'windstream' and state == 'NC':
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_41 = '1' OR fcc_coverage_{isp}_50 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_41 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed} )) "
		else:
			sql_statement += f"(fcc_coverage_{isp} = '1' AND fcc_coverage_downspeed_{isp} >= {speed}) "

	# Or local coverage is and >= speed
	if method != 'local':
		if state == 'NY':
			sql_statement += f"OR (fcc_coverage_LOCAL_altice = '1' AND fcc_coverage_downspeed_LOCAL_altice >= {speed}) ) "	
		else:
			sql_statement += f"OR (fcc_coverage_LOCAL = '1' AND fcc_coverage_downspeed_LOCAL >= {speed}) ) "
	else:
		sql_statement += ") "

	sql_statement += f"AND {is_known_res()} "

	if limit_to_tool_blocks == False:
		sql_statement += ') '
	else:
		sql_statement += f'AND ({tool_not_covered_sql(state=state,method=method,speed=speed)} OR {tool_covered_sql(state=state,speed=speed)}) ) '
		
	return sql_statement

'''
	The total count of units covered according to FCC data
'''
def fcc_covered_non_local_sql(state,speed):
	sql_statement = "( ( "
	# FCC coverage is positive and >= speed mbps for at least one 
	for i, isp in enumerate(ISPS_PER_STATE[state]):
		if i != 0:
			sql_statement += "OR "
		if isp == 'verizon' or (isp == 'centurylink' and state in ['AR','NC']):
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_50 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed})) "
		elif isp == 'att':
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_50 = '1' OR fcc_coverage_{isp}_70 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed} OR fcc_coverage_downspeed_{isp}_70 >= {speed} )) "
		elif isp == 'windstream' and state == 'NC':
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_41 = '1' OR fcc_coverage_{isp}_50 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_41 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed} )) "
		else:
			sql_statement += f"(fcc_coverage_{isp} = '1' AND fcc_coverage_downspeed_{isp} >= {speed}) "
	sql_statement += f") AND {is_known_res()} )"
	return sql_statement

'''
	The total count of units covered according to tool data
'''
def tool_not_covered_sql(state, method, speed):

	def response_codes(isp, method):
		if method == 0:
			return NEG_RESPONSES[isp]
		elif method == 1:
			return NEG_RESPONSES[isp]+UNRECOGNIZED_RESPONSES[isp]#+UNKNOWN_RESPONSES[isp]
		elif method == 2 or method == 'local':
			return NEG_RESPONSES[isp]
		elif method == 'liberal':
			return NEG_RESPONSES[isp]+UNRECOGNIZED_RESPONSES[isp]+UNKNOWN_RESPONSES[isp]
		else:
			raise Exception()

	sql_statement = f'({is_known_res()} AND ( '

	# FCC coverage is positive and > speed for at least one non-local ISP
	sql_statement += fcc_covered_non_local_sql(state=state,speed=speed)

	# FCC coverage must be 0 or < speed for all local ISPs (if method 2)
	if method != 'local':
		if state == 'NY':
			sql_statement += f"AND (fcc_coverage_LOCAL_altice = '0' OR fcc_coverage_downspeed_LOCAL_altice < {speed}) "
		else:	
			sql_statement += f"AND (fcc_coverage_LOCAL = '0' OR fcc_coverage_downspeed_LOCAL < {speed}) "

	if method == 'liberal':
		# and at least one must be: 1) adequately covered by some ISP according to fcc, 2) have not covered, unrecognized, or unknown response for the ISP
		sql_statement += "AND ( "
		for i, isp in enumerate(ISPS_PER_STATE[state]):
			if i != 0:
				sql_statement += "OR "
			if isp == 'verizon':
				sql_statement += f"( ({fcc_covers('verizon_10',speed=speed)} OR {fcc_covers('verizon_50',speed=speed)}) \
									AND (tool_coverage_verizon_10 in {response_codes(isp, method)} AND tool_coverage_verizon_50 in {response_codes(isp, method)} ) ) "
			elif isp == 'att':
				sql_statement += f"( ({fcc_covers('att_10',speed=speed)} OR {fcc_covers('att_50',speed=speed)} OR {fcc_covers('att_70',speed=speed)}) \
									AND (tool_coverage_att_10 in {response_codes(isp, method)} AND tool_coverage_att_50 in {response_codes(isp, method)} AND tool_coverage_att_70 in {response_codes(isp, method)}) ) "
			elif (isp == 'centurylink' and state in ['AR','NC']):
				sql_statement += f"( ({fcc_covers('centurylink_10',speed=speed)} OR {fcc_covers('centurylink_50',speed=speed)}) \
									AND tool_coverage_{isp} in {response_codes(isp, method)} ) "
			elif (isp == 'windstream' and state in ['NC']):
				sql_statement += f"( ({fcc_covers('windstream_10',speed=speed)} OR {fcc_covers('windstream_41',speed=speed)} or {fcc_covers('windstream_50',speed=speed)}) \
									AND tool_coverage_{isp} in {response_codes(isp, method)} ) "
			else:
				sql_statement += f"( {fcc_covers(isp,speed=speed)} AND tool_coverage_{isp} in {response_codes(isp, method)} ) "
		sql_statement += ") "
	else:
		# and at least one must be: 1) adequately covered by some ISP according to fcc, 2) not covered by that ISP
		sql_statement += "AND ( "
		for i, isp in enumerate(ISPS_PER_STATE[state]):
			if i != 0:
				sql_statement += "OR "
			if isp == 'verizon':
				sql_statement += f"( ({fcc_covers('verizon_10',speed=speed)} OR {fcc_covers('verizon_50',speed=speed)}) \
									AND (tool_coverage_verizon_10 in {NEG_RESPONSES[isp]} AND tool_coverage_verizon_50 in {NEG_RESPONSES[isp]} ) ) "
			elif isp == 'att':
				sql_statement += f"( ({fcc_covers('att_10',speed=speed)} OR {fcc_covers('att_50',speed=speed)} OR {fcc_covers('att_70',speed=speed)}) \
									AND (tool_coverage_att_10 in {NEG_RESPONSES[isp]} AND tool_coverage_att_50 in {NEG_RESPONSES[isp]} AND tool_coverage_att_70 in {NEG_RESPONSES[isp]}) ) "
			elif (isp == 'centurylink' and state in ['AR','NC']):
				sql_statement += f"( ({fcc_covers('centurylink_10',speed=speed)} OR {fcc_covers('centurylink_50',speed=speed)}) \
									AND tool_coverage_{isp} in {NEG_RESPONSES[isp]} ) "
			elif (isp == 'windstream' and state in ['NC']):
				sql_statement += f"( ({fcc_covers('windstream_10',speed=speed)} OR {fcc_covers('windstream_41',speed=speed)} OR {fcc_covers('windstream_50',speed=speed)}) \
									AND tool_coverage_{isp} in {NEG_RESPONSES[isp]} ) "
			else:
				sql_statement += f"( {fcc_covers(isp,speed=speed)} AND tool_coverage_{isp} in {NEG_RESPONSES[isp]} ) "
		sql_statement += ") "

	# and all others must be: 1) not adequately covered accord to FCC, 2) not covered accord to tool, unrecognized, or null if method 1 or not covered or null if method 2
	sql_statement += "AND ( "
	for i, isp in enumerate(ISPS_PER_STATE[state]):
		if i != 0:
			sql_statement += "AND "
		if isp == 'verizon':
			sql_statement += f"( (fcc_coverage_verizon_10 = '0' AND fcc_coverage_verizon_50 = '0') \
								OR (fcc_coverage_downspeed_verizon_10 < {speed} AND fcc_coverage_downspeed_verizon_50 < {speed}) \
								OR (tool_coverage_verizon_10 IN {response_codes(isp, method)} AND tool_coverage_verizon_50 in {response_codes(isp, method)}) ) "
		elif isp == 'att':
			sql_statement += f"( (fcc_coverage_att_10 = '0' AND fcc_coverage_att_50 = '0' AND fcc_coverage_att_70 = '0') \
								OR (fcc_coverage_downspeed_att_10 < {speed} AND fcc_coverage_downspeed_att_50 < {speed} AND fcc_coverage_downspeed_att_70 < {speed}) \
								OR (tool_coverage_att_10 IN {response_codes(isp, method)} AND tool_coverage_att_50 in {response_codes(isp, method)} AND tool_coverage_att_70 in {response_codes(isp, method)}) ) "
		elif (isp == 'centurylink' and state in ['AR','NC']):
			sql_statement += f"( (fcc_coverage_centurylink_10 = '0' AND fcc_coverage_centurylink_50 = '0') \
								OR (fcc_coverage_downspeed_centurylink_10 < {speed} AND fcc_coverage_downspeed_centurylink_50 < {speed}) \
								OR  tool_coverage_{isp} IN {response_codes(isp, method)}) "
		elif (isp == 'windstream' and state in ['NC']):
			sql_statement += f"( (fcc_coverage_windstream_10 = '0' AND fcc_coverage_windstream_41 = '0' AND fcc_coverage_windstream_50 = '0') \
								OR (fcc_coverage_windstream_10 < {speed} AND fcc_coverage_windstream_41 < {speed} AND fcc_coverage_windstream_41 < {speed}) \
								OR  tool_coverage_{isp} IN {response_codes(isp, method)}) "
		else:
			sql_statement += f"(fcc_coverage_{isp} = '0' \
								OR fcc_coverage_downspeed_{isp} < {speed} \
								OR tool_coverage_{isp} IN {response_codes(isp, method)}) "
	sql_statement += ") "

	sql_statement += ') ) '
	return sql_statement

def tool_covered_sql(state, speed):

	sql_statement = f'({is_known_res()} AND ( '

	if state == 'NY':
		sql_statement += f" (fcc_coverage_LOCAL_altice = '1' AND fcc_coverage_downspeed_LOCAL_altice >= {speed}) OR "
	else:
		sql_statement += f" (fcc_coverage_LOCAL = '1' AND fcc_coverage_downspeed_LOCAL >= {speed}) OR "

	### OR FCC is covered for one non-local ISP and is actually covered by non-local ISP
	sql_statement += '( '

	# FCC coverage is positive and > speed for at least one non-local ISP
	sql_statement += fcc_covered_non_local_sql(state=state,speed=speed)

	# and at least one must be covered
	sql_statement += "AND ( "
	for i, isp in enumerate(ISPS_PER_STATE[state]):
		if i != 0:
			sql_statement += "OR "
		if isp == 'verizon':
			sql_statement += f"( (fcc_coverage_verizon_10 = '1' OR fcc_coverage_verizon_50 = '1') \
								AND (fcc_coverage_downspeed_verizon_10 >= {speed} OR fcc_coverage_downspeed_verizon_50 >= {speed})\
								AND (tool_coverage_verizon_10 in {POS_RESPONSES[isp]} OR tool_coverage_verizon_50 in {POS_RESPONSES[isp]}) ) "
		elif isp == 'att':
			sql_statement += f"( (fcc_coverage_att_10 = '1' OR fcc_coverage_att_50 = '1' OR fcc_coverage_att_70 = '1') \
								AND (fcc_coverage_downspeed_att_10 >= {speed} OR fcc_coverage_downspeed_att_50 >= {speed} OR fcc_coverage_downspeed_att_70 >= {speed}) \
								AND (tool_coverage_att_10 in {POS_RESPONSES[isp]} OR tool_coverage_att_50 in {POS_RESPONSES[isp]} OR tool_coverage_att_70 in {POS_RESPONSES[isp]}) ) "
		elif (isp == 'centurylink' and state in ['AR','NC']):
			sql_statement += f"( (fcc_coverage_centurylink_10 = '1' OR fcc_coverage_centurylink_50 = '1') \
								AND (fcc_coverage_downspeed_centurylink_10 >= {speed} OR fcc_coverage_downspeed_centurylink_50 >= {speed})\
								AND tool_coverage_{isp} in {POS_RESPONSES[isp]} ) "
		elif (isp == 'windstream' and state in ['NC']):
			sql_statement += f"( (fcc_coverage_windstream_10 = '1' OR fcc_coverage_windstream_41 = '1' OR fcc_coverage_windstream_50 = '1') \
								AND (fcc_coverage_downspeed_windstream_10 >= {speed} OR fcc_coverage_downspeed_windstream_41 >= {speed} OR fcc_coverage_downspeed_windstream_50 >= {speed})\
								AND tool_coverage_{isp} in {POS_RESPONSES[isp]} ) "
		else:
			sql_statement += f"(fcc_coverage_{isp} = '1' \
								AND fcc_coverage_downspeed_{isp} >= {speed} \
								AND tool_coverage_{isp} in {POS_RESPONSES[isp]}) "
	sql_statement += ') '

	sql_statement += ") "

	sql_statement += ') ) '
	return sql_statement

def get_census_block_rural_classification(state, mycursor):
	sf = shapefile.Reader(f"census_blocks_rural_{state}/census_blocks_{state}.shp")
	blocks_rural_classification = dict()
	for record in sf.records():
		block = str(record['GEOID10'])
		if state == 'AR':
			block = block[1:]
		if state in blocks_rural_classification:
			raise Exception('Block appeared twice in shapefile')

		if record['UR10'] == 'U':
			blocks_rural_classification[block] = 'U'
		elif record['UR10'] == 'R':
			blocks_rural_classification[block] = 'R'
		else:
			raise Exception('Something other than rural/urban block received.')
	return blocks_rural_classification

# --------------------------------------------------------------------------------------------------

def total_coverage_rural():

	# Declare latex output and counts across states for the summary row at the bottom
	latex_output = ''
	latex_output_all_methods = '' # The latex output for methods 1 and 2 in the appendix
	combined_counts = {
		1: {
			'0': {
				'total': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'urban': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'rural': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				}
			},
			'25': {
				'total': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'urban': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'rural': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				}
			},
		},
		2: {
			'0': {
				'total': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'urban': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'rural': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				}
			},
			'25': {
				'total': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'urban': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'rural': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				}
			},
		},
		'liberal': {
			'0': {
				'total': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'urban': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'rural': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				}
			},
			'25': {
				'total': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'urban': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'rural': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				}
			},
		},'local': {
			'0': {
				'total': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'urban': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'rural': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				}
			},
			'25': {
				'total': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'urban': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				},
				'rural': {
					'fcc_total_covered_count': 0,
					'tool_total_covered_count': 0,
				}
			},
		}
	}

	summary_unit_counts ={
		'pos_count': {
			0 : {
				'total':0,
				'U':0,
				'R':0,
			},
			25 : {
				'total':0,
				'U':0,
				'R':0,
			},
		},
		'all_count': {
			0 : {
				'total':0,
				'U':0,
				'R':0,
			},
			25 : {
				'total':0,
				'U':0,
				'R':0,
			},
		}
	} 
	METHOD = 'local'

	for state in ['VT']:
		coverage_counts = total_coverage_pop_tool(state,methods=[METHOD])

		#pp.pprint(coverage_counts['25'][2]['total'])
		for method in [METHOD]:
			for speed in ['0','25']:
				for block_type in ['total','urban','rural']:
					combined_counts[method][speed][block_type]['fcc_total_covered_count'] += coverage_counts[speed][method][block_type]['fcc_total_covered_count']
					combined_counts[method][speed][block_type]['tool_total_covered_count'] += coverage_counts[speed][method][block_type]['tool_total_covered_count']
		# Add units to summary tally
		for speed in [0,25]:
			for count in ['pos_count','all_count']:
				for area_type in ['total','U','R']:
					summary_unit_counts[count][speed][area_type] += coverage_counts[str(speed)][METHOD]['count'][count][area_type]

		latex_output += \
			r"\rowcolor[HTML]{C0C0C0}" + \
			r"{} & All &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
				LABELS[state],

				# Unit counts
				coverage_counts['0'][METHOD]['count']['all_count']['total'],
				coverage_counts['0'][METHOD]['count']['pos_count']['total'],
				100* (coverage_counts['0'][METHOD]['count']['pos_count']['total'] / coverage_counts['0'][METHOD]['count']['all_count']['total']),
				coverage_counts['25'][METHOD]['count']['all_count']['total'],
				coverage_counts['25'][METHOD]['count']['pos_count']['total'],
				100* (coverage_counts['25'][METHOD]['count']['pos_count']['total'] / coverage_counts['25'][METHOD]['count']['all_count']['total']),

				coverage_counts['0'][METHOD]['total']['fcc_total_covered_count'],
				coverage_counts['0'][METHOD]['total']['tool_total_covered_count'],
				coverage_counts['0'][METHOD]['total']['tool_total_covered_percent'] * 100,
				coverage_counts['25'][METHOD]['total']['fcc_total_covered_count'],
				coverage_counts['25'][METHOD]['total']['tool_total_covered_count'],
				coverage_counts['25'][METHOD]['total']['tool_total_covered_percent'] * 100,


			) + "\n" + \
			r"      & Urban &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
				# Unit counts
				coverage_counts['0'][METHOD]['count']['all_count']['U'],
				coverage_counts['0'][METHOD]['count']['pos_count']['U'],
				100* (coverage_counts['0'][METHOD]['count']['pos_count']['U'] / coverage_counts['0'][METHOD]['count']['all_count']['U']),
				coverage_counts['25'][METHOD]['count']['all_count']['U'],
				coverage_counts['25'][METHOD]['count']['pos_count']['U'],
				100* (coverage_counts['25'][METHOD]['count']['pos_count']['U'] / coverage_counts['25'][METHOD]['count']['all_count']['U']),

				coverage_counts['0'][METHOD]['urban']['fcc_total_covered_count'],
				coverage_counts['0'][METHOD]['urban']['tool_total_covered_count'],
				coverage_counts['0'][METHOD]['urban']['tool_total_covered_percent'] * 100,
				coverage_counts['25'][METHOD]['urban']['fcc_total_covered_count'],
				coverage_counts['25'][METHOD]['urban']['tool_total_covered_count'],
				coverage_counts['25'][METHOD]['urban']['tool_total_covered_percent'] * 100,
			) + "\n" + \
			r"      & Rural &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
				# Unit counts
				coverage_counts['0'][METHOD]['count']['all_count']['R'],
				coverage_counts['0'][METHOD]['count']['pos_count']['R'],
				100* (coverage_counts['0'][METHOD]['count']['pos_count']['R'] / coverage_counts['0'][METHOD]['count']['all_count']['R']),
				coverage_counts['25'][METHOD]['count']['all_count']['R'],
				coverage_counts['25'][METHOD]['count']['pos_count']['R'],
				100* (coverage_counts['25'][METHOD]['count']['pos_count']['R'] / coverage_counts['25'][METHOD]['count']['all_count']['R']),


				coverage_counts['0'][METHOD]['rural']['fcc_total_covered_count'],
				coverage_counts['0'][METHOD]['rural']['tool_total_covered_count'],
				coverage_counts['0'][METHOD]['rural']['tool_total_covered_percent'] * 100,
				coverage_counts['25'][METHOD]['rural']['fcc_total_covered_count'],
				coverage_counts['25'][METHOD]['rural']['tool_total_covered_count'],
				coverage_counts['25'][METHOD]['rural']['tool_total_covered_percent'] * 100,
			) + "\n"

		# Latex output for both methods 1 and 2
		if False:
			latex_output_all_methods += \
				r"\rowcolor[HTML]{C0C0C0}" + \
				r"{} & All &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
					state,
					coverage_counts['0'][1]['total']['fcc_total_covered_count'],
					coverage_counts['0'][1]['total']['tool_total_covered_count'],
					coverage_counts['0'][1]['total']['tool_total_covered_percent'] * 100,
					coverage_counts['25'][1]['total']['fcc_total_covered_count'],
					coverage_counts['25'][1]['total']['tool_total_covered_count'],
					coverage_counts['25'][1]['total']['tool_total_covered_percent'] * 100,

					coverage_counts['0'][2]['total']['fcc_total_covered_count'],
					coverage_counts['0'][2]['total']['tool_total_covered_count'],
					coverage_counts['0'][2]['total']['tool_total_covered_percent'] * 100,
					coverage_counts['25'][2]['total']['fcc_total_covered_count'],
					coverage_counts['25'][2]['total']['tool_total_covered_count'],
					coverage_counts['25'][2]['total']['tool_total_covered_percent'] * 100,
				) + "\n" + \
				r"      & Urban &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
					coverage_counts['0'][1]['urban']['fcc_total_covered_count'],
					coverage_counts['0'][1]['urban']['tool_total_covered_count'],
					coverage_counts['0'][1]['urban']['tool_total_covered_percent'] * 100,
					coverage_counts['25'][1]['urban']['fcc_total_covered_count'],
					coverage_counts['25'][1]['urban']['tool_total_covered_count'],
					coverage_counts['25'][1]['urban']['tool_total_covered_percent'] * 100,

					coverage_counts['0'][2]['urban']['fcc_total_covered_count'],
					coverage_counts['0'][2]['urban']['tool_total_covered_count'],
					coverage_counts['0'][2]['urban']['tool_total_covered_percent'] * 100,
					coverage_counts['25'][2]['urban']['fcc_total_covered_count'],
					coverage_counts['25'][2]['urban']['tool_total_covered_count'],
					coverage_counts['25'][2]['urban']['tool_total_covered_percent'] * 100,
				) + "\n" + \
				r"      & Rural &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
					coverage_counts['0'][1]['rural']['fcc_total_covered_count'],
					coverage_counts['0'][1]['rural']['tool_total_covered_count'],
					coverage_counts['0'][1]['rural']['tool_total_covered_percent'] * 100,
					coverage_counts['25'][1]['rural']['fcc_total_covered_count'],
					coverage_counts['25'][1]['rural']['tool_total_covered_count'],
					coverage_counts['25'][1]['rural']['tool_total_covered_percent'] * 100,

					coverage_counts['0'][2]['rural']['fcc_total_covered_count'],
					coverage_counts['0'][2]['rural']['tool_total_covered_count'],
					coverage_counts['0'][2]['rural']['tool_total_covered_percent'] * 100,
					coverage_counts['25'][2]['rural']['fcc_total_covered_count'],
					coverage_counts['25'][2]['rural']['tool_total_covered_count'],
					coverage_counts['25'][2]['rural']['tool_total_covered_percent'] * 100,
				) + "\n"

	# Add summary row on bottom
	summary_unit_counts[count][speed][area_type] 
	latex_output += \
			r"\rowcolor[HTML]{C0C0C0}" + \
			r"Total & All &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
				# Units
				summary_unit_counts['all_count'][0]['total'], 
				summary_unit_counts['pos_count'][0]['total'],
				100 * (summary_unit_counts['pos_count'][0]['total']/ summary_unit_counts['all_count'][0]['total']),
				summary_unit_counts['all_count'][25]['total'], 
				summary_unit_counts['pos_count'][25]['total'],
				100 * (summary_unit_counts['pos_count'][25]['total']/ summary_unit_counts['all_count'][25]['total']),

				combined_counts[METHOD]['0']['total']['fcc_total_covered_count'],
				combined_counts[METHOD]['0']['total']['tool_total_covered_count'],
				(combined_counts[METHOD]['0']['total']['tool_total_covered_count'] / combined_counts[METHOD]['0']['total']['fcc_total_covered_count']) * 100,
				combined_counts[METHOD]['25']['total']['fcc_total_covered_count'],
				combined_counts[METHOD]['25']['total']['tool_total_covered_count'],
				(combined_counts[METHOD]['25']['total']['tool_total_covered_count'] / combined_counts[METHOD]['25']['total']['fcc_total_covered_count']) * 100,
			) + "\n" + \
			r"      & Urban &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
				# Units
				summary_unit_counts['all_count'][0]['U'], 
				summary_unit_counts['pos_count'][0]['U'],
				100 * (summary_unit_counts['pos_count'][0]['U']/ summary_unit_counts['all_count'][0]['U']),
				summary_unit_counts['all_count'][25]['U'], 
				summary_unit_counts['pos_count'][25]['U'],
				100 * (summary_unit_counts['pos_count'][25]['U']/ summary_unit_counts['all_count'][25]['U']),

				combined_counts[METHOD]['0']['urban']['fcc_total_covered_count'],
				combined_counts[METHOD]['0']['urban']['tool_total_covered_count'],
				(combined_counts[METHOD]['0']['urban']['tool_total_covered_count'] / combined_counts[METHOD]['0']['urban']['fcc_total_covered_count']) * 100,
				combined_counts[METHOD]['25']['urban']['fcc_total_covered_count'],
				combined_counts[METHOD]['25']['urban']['tool_total_covered_count'],
				(combined_counts[METHOD]['25']['urban']['tool_total_covered_count'] / combined_counts[METHOD]['25']['urban']['fcc_total_covered_count']) * 100,
			) + "\n" + \
			r"      & Rural &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
				# Units
				summary_unit_counts['all_count'][0]['R'], 
				summary_unit_counts['pos_count'][0]['R'],
				100 * (summary_unit_counts['pos_count'][0]['R']/ summary_unit_counts['all_count'][0]['R']),
				summary_unit_counts['all_count'][25]['R'], 
				summary_unit_counts['pos_count'][25]['R'],
				100 * (summary_unit_counts['pos_count'][25]['R']/ summary_unit_counts['all_count'][25]['R']),

				combined_counts[METHOD]['0']['rural']['fcc_total_covered_count'],
				combined_counts[METHOD]['0']['rural']['tool_total_covered_count'],
				(combined_counts[METHOD]['0']['rural']['tool_total_covered_count'] / combined_counts[METHOD]['0']['rural']['fcc_total_covered_count']) * 100,
				combined_counts[METHOD]['25']['rural']['fcc_total_covered_count'],
				combined_counts[METHOD]['25']['rural']['tool_total_covered_count'],
				(combined_counts[METHOD]['25']['rural']['tool_total_covered_count'] / combined_counts[METHOD]['25']['rural']['fcc_total_covered_count']) * 100,
			) + "\n"

	if False:
		latex_output_all_methods += \
				r"\rowcolor[HTML]{C0C0C0}" + \
				r"Total & All &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
					combined_counts[1]['0']['total']['fcc_total_covered_count'],
					combined_counts[1]['0']['total']['tool_total_covered_count'],
					(combined_counts[1]['0']['total']['tool_total_covered_count'] / combined_counts[1]['0']['total']['fcc_total_covered_count']) * 100,
					combined_counts[1]['25']['total']['fcc_total_covered_count'],
					combined_counts[1]['25']['total']['tool_total_covered_count'],
					(combined_counts[1]['25']['total']['tool_total_covered_count'] / combined_counts[1]['25']['total']['fcc_total_covered_count']) * 100,

					combined_counts[2]['0']['total']['fcc_total_covered_count'],
					combined_counts[2]['0']['total']['tool_total_covered_count'],
					(combined_counts[2]['0']['total']['tool_total_covered_count'] / combined_counts[2]['0']['total']['fcc_total_covered_count']) * 100,
					combined_counts[2]['25']['total']['fcc_total_covered_count'],
					combined_counts[2]['25']['total']['tool_total_covered_count'],
					(combined_counts[2]['25']['total']['tool_total_covered_count'] / combined_counts[2]['25']['total']['fcc_total_covered_count']) * 100,
				) + "\n" + \
				r"      & Urban &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
					combined_counts[1]['0']['urban']['fcc_total_covered_count'],
					combined_counts[1]['0']['urban']['tool_total_covered_count'],
					(combined_counts[1]['0']['urban']['tool_total_covered_count'] / combined_counts[1]['0']['urban']['fcc_total_covered_count']) * 100,
					combined_counts[1]['25']['urban']['fcc_total_covered_count'],
					combined_counts[1]['25']['urban']['tool_total_covered_count'],
					(combined_counts[1]['25']['urban']['tool_total_covered_count'] / combined_counts[1]['25']['urban']['fcc_total_covered_count']) * 100,

					combined_counts[2]['0']['urban']['fcc_total_covered_count'],
					combined_counts[2]['0']['urban']['tool_total_covered_count'],
					(combined_counts[2]['0']['urban']['tool_total_covered_count'] / combined_counts[2]['0']['urban']['fcc_total_covered_count']) * 100,
					combined_counts[2]['25']['urban']['fcc_total_covered_count'],
					combined_counts[2]['25']['urban']['tool_total_covered_count'],
					(combined_counts[2]['25']['urban']['tool_total_covered_count'] / combined_counts[2]['25']['urban']['fcc_total_covered_count']) * 100,
				) + "\n" + \
				r"      & Rural &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% &  {:,} & {:,} & {:.2f}\% & {:,} & {:,} & {:.2f}\% \\".format(
					combined_counts[1]['0']['rural']['fcc_total_covered_count'],
					combined_counts[1]['0']['rural']['tool_total_covered_count'],
					(combined_counts[1]['0']['rural']['tool_total_covered_count'] / combined_counts[1]['0']['rural']['fcc_total_covered_count']) * 100,
					combined_counts[1]['25']['rural']['fcc_total_covered_count'],
					combined_counts[1]['25']['rural']['tool_total_covered_count'],
					(combined_counts[1]['25']['rural']['tool_total_covered_count'] / combined_counts[1]['25']['rural']['fcc_total_covered_count']) * 100,

					combined_counts[2]['0']['rural']['fcc_total_covered_count'],
					combined_counts[2]['0']['rural']['tool_total_covered_count'],
					(combined_counts[2]['0']['rural']['tool_total_covered_count'] / combined_counts[2]['0']['rural']['fcc_total_covered_count']) * 100,
					combined_counts[2]['25']['rural']['fcc_total_covered_count'],
					combined_counts[2]['25']['rural']['tool_total_covered_count'],
					(combined_counts[2]['25']['rural']['tool_total_covered_count'] / combined_counts[2]['25']['rural']['fcc_total_covered_count']) * 100,
				) + "\n"

	print('Just method 2 (main paper):')
	print(latex_output)

	if False:
		print('Both methods 1 and 2 (appendix):')
		print(latex_output_all_methods)

# --------------------------------------------------------------------------------------------------

def get_bad_blocks(state,isp):
	print('-------------------------STATE: {}-------------------------'.format(state))
	# Connect to mysql database
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)

	mycursor = mydb.cursor(buffered=True)

	mycursor.execute(f"SELECT addr_census_block, tool_coverage_{isp}, count(*) FROM addresses_{state} WHERE fcc_coverage_{isp} = '1' GROUP BY addr_census_block, tool_coverage_{isp}")
	results = mycursor.fetchall()

	for i, row in enumerate(results):
		print(row)

		if i == 20:
			break
			

	# Get counts
# Compute summary statistics
def coverage_summary(state):
	print('-------------------------STATE: {}-------------------------'.format(state))
	# Connect to mysql database
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)
	speed = '0' # MAKE THIS PARAMETER

	latex_output = ''
	results = dict()

	for isp in ISPS_PER_STATE[state]:

		results[isp] = dict()
		response_counts = dict()
		if isp == 'verizon':
			
			# Get total FCC covered count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)})")
			fcc_total_count = mycursor.fetchall()[0][0]

			# Get positive count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and (tool_coverage_{isp}_10 = '1' or tool_coverage_{isp}_50 = '1')")
			pos_count = mycursor.fetchall()[0][0]

			# Get negative count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and ((tool_coverage_{isp}_10 = '0' and tool_coverage_{isp}_50 = '0') or (tool_coverage_{isp}_10 = '21' and tool_coverage_{isp}_50 = '21'))")
			neg_count = mycursor.fetchall()[0][0]

			# Get not recognized count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and (tool_coverage_{isp}_10 = '4' and tool_coverage_{isp}_50 = '4')")
			unrecognized_count = mycursor.fetchall()[0][0]

			# Get excluded count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and ((tool_coverage_{isp}_10 = '20' and tool_coverage_{isp}_50 = '20') or (tool_coverage_{isp}_10 = '22' and tool_coverage_{isp}_50 = '22'))")
			excluded_count = mycursor.fetchall()[0][0]

		elif isp == 'att':
			# Get total FCC covered count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)})")
			fcc_total_count = mycursor.fetchall()[0][0]

			# Get positive count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)}) and (tool_coverage_{isp}_10 in ('2','3') or tool_coverage_{isp}_50 in ('2','3') or tool_coverage_{isp}_70 in ('2','3'))")
			pos_count = mycursor.fetchall()[0][0]

			# Get negative count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)}) and (tool_coverage_{isp}_10 = '0' and tool_coverage_{isp}_50 = '0' and tool_coverage_{isp}_70 = '0')")
			neg_count = mycursor.fetchall()[0][0]

			# Get not recognized count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)}) and (tool_coverage_{isp}_10 = '4' and tool_coverage_{isp}_50 = '4' and tool_coverage_{isp}_70 = '4')")
			unrecognized_count = mycursor.fetchall()[0][0]

			# Get excluded count
			mycursor.execute(f"SELECT count(*) FROM addresses_{state} WHERE ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)}) and (tool_coverage_{isp}_10 in ('23', '24', '25', '26', '27', '30', '101') and tool_coverage_{isp}_50 in ('23', '24', '25', '26', '27', '30', '101') and tool_coverage_{isp}_70 in ('23', '24', '25', '26', '27', '30', '101'))")
			excluded_count = mycursor.fetchall()[0][0]

		else:
			if state == 'AR' and isp == 'centurylink':
				mycursor.execute(f"SELECT tool_coverage_{isp}, count(*)  FROM addresses_{state} WHERE ({fcc_covers('centurylink_10',speed)} or {fcc_covers('centurylink_50',speed)}) GROUP BY tool_coverage_centurylink")
			else:
				mycursor.execute(f"SELECT tool_coverage_{isp}, count(*)  FROM addresses_{state} WHERE {fcc_covers(isp, speed)} GROUP BY tool_coverage_{isp}")

			myresult = mycursor.fetchall()
			result = ()
			for i,row in enumerate(myresult):
				if row[0] == None or row[0] == '7':
					continue
				response_counts[row[0]] = row[1]
				result = result + (row[0],)
			print(sorted(result))


			pp.pprint(response_counts)

			# Get positive count
			pos_count = 0
			for response in POS_RESPONSES[isp]:
				if response != NULL:
					pos_count += response_counts[response]

			# Get negative count
			neg_count = 0
			for response in NEG_RESPONSES[isp]:
				if response != NULL:
					neg_count += response_counts[response]

			# Get Unrecognized count
			unrecognized_count = 0
			for response in UNRECOGNIZED_RESPONSES[isp]:
				if response != NULL:
					unrecognized_count += response_counts[response]

			# Get excluded count
			excluded_count = 0
			for response in EXCLUDED_RESPONSES[isp]:
				if response != NULL and response in response_counts:
					excluded_count += response_counts[response]

			# Get business count
			business_count = 0
			for response in BUSINESS_RESPONSES[isp]:
				if response != NULL:
					business_count += response_counts[response]

		# ----

		# Print positive/negative counts and percentages

		total_pos_neg = pos_count + neg_count
		neg_percent = (neg_count/total_pos_neg) * 100
		pos_percent = (pos_count/total_pos_neg) * 100

		print('ISP: {}'.format(isp))
		print('Positive Count: {:,} ({:.1f}%)'.format(pos_count, pos_percent))
		print('Negative Count: {:,} ({:.1f}%)'.format(neg_count, neg_percent))

		# Print unrecognized and excluded counts
		print('Unrecognized Count: {:,}'.format(unrecognized_count))
		print('Excluded Count: {:,}'.format(excluded_count))
		print()
		results[isp] = {
			'pos_count' : pos_count,
			'neg_count' : neg_count,
			'unrecognized_count' : unrecognized_count,
			'excluded_count' : excluded_count,
		}

		# Make Latex Table
		'''
		isp_name = LABELS[isp]
		if isp_name == 'AT&T':
			isp_name = 'AT\&T'
		latex_output += '{},'.format(isp_name) + '{' + '{:,}'.format(pos_count) + '},' + '{:.2f}\%,'.format(pos_percent) + '{' + '{:,}'.format(neg_count) + '},' + '{:.2f}\%,'.format(neg_percent) + '{' + '{:,}'.format(unrecognized_count) + '},' + '{' + '{:,}'.format(excluded_count) + '}\n'
		'''
	return results
	#return latex_output


def get_urban_rural_count_per_code(rows, blocks_rural_classification):
	counts = {'U': 0, 'R': 0}
	counts_per_block = defaultdict(lambda:0)
	for row in rows:
		block = row[0]
		count = row[1]

		urban_or_rural = blocks_rural_classification[block]
		counts[urban_or_rural] += count
		counts_per_block[block] += count
	return counts, counts_per_block



# Get number of covered/not-covered/unrecognized/excluded houses for each ISP in state
# Broken down by urban/rural
def coverage_summary_urban_rural(state, speed):
	print('-------------------------STATE: {}-------------------------'.format(state))
	# Connect to mysql database
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)
	#speed = 0

	blocks_rural_classification = get_census_block_rural_classification(state,mycursor)

	# Get population of each census block
	blocks_pop = get_census_block_population_counts(state, mycursor)
	
	latex_output = ''
	results = dict()

	for isp in ISPS_PER_STATE[state]:

		results[isp] = dict()
		response_counts = {'U': defaultdict(lambda: 0), 'R': defaultdict(lambda: 0)}
		if isp == 'verizon':
			# Get positive count
			mycursor.execute(f"SELECT addr_census_block, count(*) FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and (tool_coverage_{isp}_10 in {POS_RESPONSES[isp]} or tool_coverage_{isp}_50 in {POS_RESPONSES[isp]}) GROUP BY addr_census_block")
			pos_count, pos_count_per_block = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

			# Get negative count
			mycursor.execute(f"SELECT addr_census_block, count(*) FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and (tool_coverage_{isp}_10 in {NEG_RESPONSES[isp]} and tool_coverage_{isp}_50 in {NEG_RESPONSES[isp]}) GROUP BY addr_census_block")
			neg_count, neg_count_per_block = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

			# Get not recognized count
			mycursor.execute(f"SELECT addr_census_block, count(*) FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and (tool_coverage_{isp}_10 in {UNRECOGNIZED_RESPONSES[isp]} and tool_coverage_{isp}_50 in {UNRECOGNIZED_RESPONSES[isp]}) GROUP BY addr_census_block")
			unrecognized_count,_ = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

			# Get business count
			mycursor.execute(f"SELECT addr_census_block, count(*) FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and (tool_coverage_{isp}_10 in {BUSINESS_RESPONSES[isp]} and tool_coverage_{isp}_50 in {BUSINESS_RESPONSES[isp]}) GROUP BY addr_census_block")
			business_count,_ = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

			# Get excluded count
			mycursor.execute(f"SELECT addr_census_block, count(*) FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)}) and (tool_coverage_{isp}_10 in {EXCLUDED_RESPONSES[isp]} and tool_coverage_{isp}_50 in {EXCLUDED_RESPONSES[isp]}) GROUP BY addr_census_block".format(state,isp,isp,isp,isp, isp, isp))
			excluded_count,_ = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

		elif isp == 'att':
			# Get positive count
			mycursor.execute(f"SELECT addr_census_block, count(*) FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)}) and (tool_coverage_{isp}_10 in {POS_RESPONSES[isp]} or tool_coverage_{isp}_50 in {POS_RESPONSES[isp]} or tool_coverage_{isp}_70 in {POS_RESPONSES[isp]}) GROUP BY addr_census_block")
			pos_count,pos_count_per_block = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

			# Get negative count
			mycursor.execute(f"SELECT addr_census_block, count(*)FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)}) and (tool_coverage_{isp}_10 in {NEG_RESPONSES[isp]} and tool_coverage_{isp}_50 in {NEG_RESPONSES[isp]} and tool_coverage_{isp}_70 in {NEG_RESPONSES[isp]}) GROUP BY addr_census_block")
			neg_count,neg_count_per_block = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

			# Get not recognized count
			mycursor.execute(f"SELECT addr_census_block, count(*)FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)})and (tool_coverage_{isp}_10 in {UNRECOGNIZED_RESPONSES[isp]} and tool_coverage_{isp}_50 in {UNRECOGNIZED_RESPONSES[isp]} and tool_coverage_{isp}_70 in {UNRECOGNIZED_RESPONSES[isp]}) GROUP BY addr_census_block")
			unrecognized_count,_ = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

			# Get business count
			mycursor.execute(f"SELECT addr_census_block, count(*)FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)})and (tool_coverage_{isp}_10 in {BUSINESS_RESPONSES[isp]} and tool_coverage_{isp}_50 in {BUSINESS_RESPONSES[isp]} and tool_coverage_{isp}_70 in {BUSINESS_RESPONSES[isp]}) GROUP BY addr_census_block")
			business_count,_ = get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

			# Get excluded count
			mycursor.execute(f"SELECT addr_census_block, count(*) FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers(isp + '_10',speed)} or {fcc_covers(isp + '_50',speed)} or {fcc_covers(isp + '_70',speed)}) and (tool_coverage_{isp}_10 in {EXCLUDED_RESPONSES[isp]} and tool_coverage_{isp}_50 in {EXCLUDED_RESPONSES[isp]} and tool_coverage_{isp}_70 in {EXCLUDED_RESPONSES[isp]}) GROUP BY addr_census_block")
			excluded_count,_ =get_urban_rural_count_per_code(mycursor.fetchall(), blocks_rural_classification)

		else:
			if state in ['AR','NC'] and isp == 'centurylink':
				mycursor.execute(f"SELECT tool_coverage_{isp}, count(*), addr_census_block FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers('centurylink_10',speed)} or {fcc_covers('centurylink_50',speed)}) GROUP BY tool_coverage_centurylink, addr_census_block")
			elif state in ['NC'] and isp == 'windstream':
				mycursor.execute(f"SELECT tool_coverage_{isp}, count(*), addr_census_block FROM addresses_{state} WHERE ({is_known_res()}) AND ({fcc_covers('windstream_10',speed)} or {fcc_covers('windstream_41',speed)} or {fcc_covers('windstream_50',speed)}) GROUP BY tool_coverage_{isp}, addr_census_block")
			else:
				mycursor.execute(f"SELECT tool_coverage_{isp}, count(*), addr_census_block FROM addresses_{state} WHERE ({is_known_res()}) AND {fcc_covers(isp, speed)} GROUP BY tool_coverage_{isp}, addr_census_block")

			myresult = mycursor.fetchall()

			# Positive count and negative count per block
			pos_count_per_block = defaultdict(lambda: 0)
			neg_count_per_block = defaultdict(lambda: 0)

			# Get counts for each code, broken down by urban/rural
			for i,row in enumerate(myresult):
				tool_code = row[0]
				count = row[1]
				census_block = row[2]
				urban_or_rural = blocks_rural_classification[census_block]

				if tool_code == None or tool_code == '7':
					continue

				response_counts[urban_or_rural][tool_code] += count

				if tool_code in POS_RESPONSES[isp]:
					pos_count_per_block[census_block] += count
				if tool_code in NEG_RESPONSES[isp]:
					neg_count_per_block[census_block] += count
			pp.pprint(response_counts)

			# Get positive count
			pos_count = {'U': 0, 'R': 0}
			for response in POS_RESPONSES[isp]:
				if response != NULL:
					pos_count['U'] += response_counts['U'][response]
					pos_count['R'] += response_counts['R'][response]


			# Get negative count
			neg_count = {'U': 0, 'R': 0}
			for response in NEG_RESPONSES[isp]:
				if response != NULL:
					neg_count['U'] += response_counts['U'][response]
					neg_count['R'] += response_counts['R'][response]

			# Get Unrecognized count
			unrecognized_count = {'U': 0, 'R': 0}
			for response in UNRECOGNIZED_RESPONSES[isp]:
				if response != NULL:
					unrecognized_count['U'] += response_counts['U'][response]
					unrecognized_count['R'] += response_counts['R'][response]

			# Get excluded count
			excluded_count = {'U': 0, 'R': 0}
			for response in EXCLUDED_RESPONSES[isp]:
				if response != NULL:
					excluded_count['U'] += response_counts['U'][response]
					excluded_count['R'] += response_counts['R'][response]

			# Get business count
			business_count = {'U': 0, 'R': 0}
			for response in BUSINESS_RESPONSES[isp]:
				if response != NULL:
					business_count['U'] += response_counts['U'][response]
					business_count['R'] += response_counts['R'][response]

		# ----

		### covered pop for the ISP

		# Get coverage ratio per block
		ratio_per_block = dict()
		for block in set(list(neg_count_per_block.keys()) + list(pos_count_per_block.keys())):
			if neg_count_per_block[block] == 0 and pos_count_per_block[block] == 0:
				raise Exception()
			ratio_per_block[block] = pos_count_per_block[block] / (pos_count_per_block[block] + neg_count_per_block[block] )
			#print(ratio_per_block[block])

		# Get covered pop per bloock from ratio per block
		covered_pop = {
			'U': 0,
			'R': 0,
			'total': 0,
		}
		total_pop = {
			'U': 0,
			'R': 0,
			'total': 0,
		}
		for block, ratio in ratio_per_block.items():
			urban_or_rural = blocks_rural_classification[block]
			covered_pop[urban_or_rural] += int(blocks_pop[block] * ratio)
			total_pop[urban_or_rural] += int(blocks_pop[block])


			covered_pop['total'] += int(blocks_pop[block] * ratio)
			total_pop['total'] += int(blocks_pop[block])

		# Print positive/negative counts and percentages
		print('ISP: {}'.format(isp))
		results[isp] = dict()
		for urban_or_rural in ['U', 'R']:
			if pos_count[urban_or_rural] == 0 and neg_count[urban_or_rural] == 0:
				total_pos_neg = 0
				neg_percent = 0
				pos_percent = 0
			else:
				total_pos_neg = pos_count[urban_or_rural] + neg_count[urban_or_rural]
				neg_percent = (neg_count[urban_or_rural]/total_pos_neg) * 100
				pos_percent = (pos_count[urban_or_rural]/total_pos_neg) * 100

			print('{}'.format(urban_or_rural))
			print('Positive Count: {:,} ({:.1f}%)'.format(pos_count[urban_or_rural], pos_percent))
			print('Negative Count: {:,} ({:.1f}%)'.format(neg_count[urban_or_rural], neg_percent))

			# Print unrecognized and excluded counts
			print('Unrecognized Count: {:,}'.format(unrecognized_count[urban_or_rural]))
			print('Business Count: {:,}'.format(business_count[urban_or_rural]))
			print('Excluded Count: {:,}'.format(excluded_count[urban_or_rural]))
			print()
			results[isp][urban_or_rural] = {
				'pos_count' : pos_count[urban_or_rural],
				'neg_count' : neg_count[urban_or_rural],
				'unrecognized_count' : unrecognized_count[urban_or_rural],
				'excluded_count' : excluded_count[urban_or_rural],
				'business_count' : business_count[urban_or_rural],
			}
			results[isp]['pop'] = {
				'covered_pop': covered_pop,
				'total_pop': total_pop,
			}

		# Make Latex Table
		'''
		isp_name = LABELS[isp]
		if isp_name == 'AT&T':
			isp_name = 'AT\&T'
		latex_output += '{},'.format(isp_name) + '{' + '{:,}'.format(pos_count) + '},' + '{:.2f}\%,'.format(pos_percent) + '{' + '{:,}'.format(neg_count) + '},' + '{:.2f}\%,'.format(neg_percent) + '{' + '{:,}'.format(unrecognized_count) + '},' + '{' + '{:,}'.format(excluded_count) + '}\n'
		'''
	return results

def coverage_isp():
	coverage_counts_per_isp = defaultdict(lambda: defaultdict(lambda: 0))
	latex_output = ''

	for state in STATES:
		# Get coverage counts for each isp in 'state'
		coverages_state = coverage_summary(state)

		# Add these coverage counts to each ISP's total count
		for isp, coverage_counts in coverages_state.items():
			coverage_counts_per_isp[isp]['pos_count'] += coverage_counts['pos_count']
			coverage_counts_per_isp[isp]['neg_count'] += coverage_counts['neg_count']
			coverage_counts_per_isp[isp]['unrecognized_count'] += coverage_counts['unrecognized_count']
			coverage_counts_per_isp[isp]['excluded_count'] += coverage_counts['excluded_count']

	# Print each ISP's total count
	for isp, coverage_counts in coverage_counts_per_isp.items():
		isp_name = LABELS[isp]
		if isp_name == 'AT&T':
			isp_name = 'AT\&T'
		#latex_output += '{},'.format(isp_name) + '{' + '{:,}'.format(coverage_counts['pos_count']) + '},' + '{:.2f}\%,'.format( (coverage_counts['pos_count']/(coverage_counts['pos_count']+coverage_counts['neg_count']))*100   ) + '{' + '{:,}'.format(coverage_counts['neg_count']) + '},' + '{:.2f}\%,'.format( (coverage_counts['neg_count']/(coverage_counts['pos_count']+coverage_counts['neg_count']))*100 ) + '\n'
		latex_output += r"\hline \textbf{" + isp_name + "} & " + '{:,}'.format(coverage_counts['pos_count']) + "& " + '{:.2f}'.format( (coverage_counts['pos_count']/(coverage_counts['pos_count']+coverage_counts['neg_count']))*100   ) + r"$\%$ &" +  '{:,}'.format(coverage_counts['neg_count'])  + "& " + '{:.2f}'.format( (coverage_counts['neg_count']/(coverage_counts['pos_count']+coverage_counts['neg_count']))*100 ) + r"$\%$ \\" + '\n'
	pp.pprint(coverage_counts_per_isp)
	print(latex_output)

# Get coverage per ISP broken down by urban/rural blocks
def coverage_isp_rural():
	DOING_SPEED_PLOT = False # make this TRUE when plotting coverage at the various speeds (takes a long time because it's rerun for so many speeds)

	isp_counts_per_speed = dict()
	if DOING_SPEED_PLOT:
		speeds = [0,25,50,100,200]
	else:
		speeds = [0,25]
	summary_count = dict()
	for speed in speeds:
		summary_count[speed] =  {
			'U': defaultdict(lambda: 0),
			'R': defaultdict(lambda: 0),
		}
		summary_count[speed]['pop'] = {
			'covered_pop' : {
				'U': 0,
				'R': 0,
				'total': 0,
			}, 
			'total_pop' : {
				'U': 0,
				'R': 0,
				'total': 0,
			}
	}
	latex_output = ''
	latex_output_full = ''
	for speed in speeds:
		print('-----------------------------------------------')
		print('----------------SPEED: {}------------------------'.format(speed))
		print('-----------------------------------------------')

		coverage_counts_per_isp =  defaultdict(lambda:{
			'U': defaultdict(lambda: 0),
			'R': defaultdict(lambda: 0),
			'pop': {
				'covered_pop' : {
					'U': 0,
					'R': 0,
					'total': 0,
				}, 
				'total_pop' : {
					'U': 0,
					'R': 0,
					'total': 0,
				}
			}
		})

		for state in STATES:
			# Get coverage counts for each isp in 'state'
			coverages_state = coverage_summary_urban_rural(state,speed)

			'''
			coverage_counts_per_isp = {
				isp: {
					covered_pop = {
						'U': 0,
						'R': 0,
						'total': 0,
					}
					total_pop = {
						'U': 0,
						'R': 0,
						'total': 0,
					}
				}
			}
			'''

			# Add pop counts
			for isp in coverages_state.keys():
				for pop in ['covered_pop','total_pop']:
					for area_type in ['U','R','total']:
						coverage_counts_per_isp[isp]['pop'][pop][area_type] += coverages_state[isp]['pop'][pop][area_type]

			# Add these coverage counts to each ISP's total count
			for urban_or_rural in ['U','R']:
				for isp, coverage_counts in coverages_state.items():
					coverage_counts_per_isp[isp][urban_or_rural]['pos_count'] += coverage_counts[urban_or_rural]['pos_count']
					coverage_counts_per_isp[isp][urban_or_rural]['neg_count'] += coverage_counts[urban_or_rural]['neg_count']
					coverage_counts_per_isp[isp][urban_or_rural]['unrecognized_count'] += coverage_counts[urban_or_rural]['unrecognized_count']
					coverage_counts_per_isp[isp][urban_or_rural]['excluded_count'] += coverage_counts[urban_or_rural]['excluded_count']
					coverage_counts_per_isp[isp][urban_or_rural]['business_count'] += coverage_counts[urban_or_rural]['business_count']

					# Add to summary count
					summary_count[speed][urban_or_rural]['pos_count'] += coverage_counts[urban_or_rural]['pos_count']
					summary_count[speed][urban_or_rural]['neg_count'] += coverage_counts[urban_or_rural]['neg_count']
					summary_count[speed][urban_or_rural]['unrecognized_count'] += coverage_counts[urban_or_rural]['unrecognized_count']
					summary_count[speed][urban_or_rural]['excluded_count'] += coverage_counts[urban_or_rural]['excluded_count']
					summary_count[speed][urban_or_rural]['business_count'] += coverage_counts[urban_or_rural]['business_count']

			# Add state to summary count for pop
			'''
			summary_count[speed]['pop'] = {
				'covered_pop' : {
					'U': 0,
					'R': 0,
					'total': 0,
				}, 
				'total_pop' : {
					'U': 0,
					'R': 0,
					'total': 0,
				}
			}
			'''
			for isp in coverages_state:
				for pop_type in ['covered_pop', 'total_pop']:
					for area_type in ['U','R','total']:
						summary_count[speed]['pop'][pop_type][area_type] += coverages_state[isp]['pop'][pop_type][area_type]
		
		
		isp_counts_per_speed[speed] = coverage_counts_per_isp
	print('-----------------------------------------')

	# Print each ISP's total count
	for isp in sorted(coverage_counts_per_isp):
		print('Total count of {}...'.format(isp))
		isp_name = LABELS[isp]
		if isp_name == 'AT&T':
			isp_name = 'AT\&T'

		counts = dict()
		for speed in speeds:
			counts[speed] = dict()

		for speed in speeds:
			counts[speed]['total_pos_neg_count'] = isp_counts_per_speed[speed][isp]['U']['pos_count'] + isp_counts_per_speed[speed][isp]['R']['pos_count'] + isp_counts_per_speed[speed][isp]['U']['neg_count'] + isp_counts_per_speed[speed][isp]['R']['neg_count']
			counts[speed]['urban_pos_neg_count'] = isp_counts_per_speed[speed][isp]['U']['pos_count'] +isp_counts_per_speed[speed][isp]['U']['neg_count']
			counts[speed]['rural_pos_neg_count'] = isp_counts_per_speed[speed][isp]['R']['pos_count'] +isp_counts_per_speed[speed][isp]['R']['neg_count'] 

		percents = dict()
		for speed in speeds:
			if counts[speed]['total_pos_neg_count'] != 0:
				#print('HERE')
				#pp.pprint(counts[speed]['total_pos_neg_count'])
				percents[speed] = {
					'total': 100*((isp_counts_per_speed[speed][isp]['U']['pos_count'] + isp_counts_per_speed[speed][isp]['R']['pos_count']) / counts[speed]['total_pos_neg_count']),
					'U': 100*(isp_counts_per_speed[speed][isp]['U']['pos_count'] / counts[speed]['urban_pos_neg_count']),
					'R': 100*(isp_counts_per_speed[speed][isp]['R']['pos_count'] / counts[speed]['rural_pos_neg_count']),
				}
			else:
				percents[speed] = {
					'total': -1,
					'U': -1,
					'R': -1,
				}

		if isp_counts_per_speed[25][isp]['pop']['total_pop']['total'] != 0:
			pop_25_percent = {
				'total': 100* (isp_counts_per_speed[25][isp]['pop']['covered_pop']['total']/isp_counts_per_speed[25][isp]['pop']['total_pop']['total']),
				'U': 100* (isp_counts_per_speed[25][isp]['pop']['covered_pop']['U']/isp_counts_per_speed[25][isp]['pop']['total_pop']['U']),
				'R': 100* (isp_counts_per_speed[25][isp]['pop']['covered_pop']['R']/isp_counts_per_speed[25][isp]['pop']['total_pop']['R']),
			}
		else:
			pop_25_percent = {
				'total': 0,
				'U': 0,
				'R': 0,
			}

		# Print this ISP's row in the latex output

		# Adds to the latex output for just positive/negative
		latex_output += \
			r"\rowcolor[HTML]{C0C0C0} " + '\n' + \
			r"{} & All &  {:,} & {:,} & {:.0f}\% & {:,} & {:,} & {:.0f}\% &  {:,} & {:,} & {:.0f}\% & {:,} & {:,} & {:.0f}\% \\ ".format(
				isp_name,
				counts[0]['total_pos_neg_count'],
				isp_counts_per_speed[0][isp]['U']['pos_count'] + isp_counts_per_speed[0][isp]['R']['pos_count'],
				percents[0]['total'], #100*((isp_counts_per_speed['0'][isp]['U']['pos_count'] + isp_counts_per_speed['0'][isp]['R']['pos_count']) / counts['0']['total_pos_neg_count']),
				counts[25]['total_pos_neg_count'],
				isp_counts_per_speed[25][isp]['U']['pos_count'] + isp_counts_per_speed[25][isp]['R']['pos_count'],
				percents[25]['total'], #100*((isp_counts_per_speed['25'][isp]['U']['pos_count'] + isp_counts_per_speed['25'][isp]['R']['pos_count']) / counts['25']['total_pos_neg_count']),

				# Pop info
				isp_counts_per_speed[0][isp]['pop']['total_pop']['total'],
				isp_counts_per_speed[0][isp]['pop']['covered_pop']['total'],
				100* (isp_counts_per_speed[0][isp]['pop']['covered_pop']['total']/isp_counts_per_speed[0][isp]['pop']['total_pop']['total']),
				isp_counts_per_speed[25][isp]['pop']['total_pop']['total'],
				isp_counts_per_speed[25][isp]['pop']['covered_pop']['total'],
				pop_25_percent['total'],#100* (isp_counts_per_speed[25][isp]['pop']['covered_pop']['total']/isp_counts_per_speed[25][isp]['pop']['total_pop']['total']),


			) + '\n' + \
			r"            & Urban &  {:,} & {:,} & {:.0f}\% & {:,} &  {:,} & {:.0f}\% &  {:,} & {:,} & {:.0f}\% & {:,} & {:,} & {:.0f}\%  \\ ".format(
				counts[0]['urban_pos_neg_count'],
				isp_counts_per_speed[0][isp]['U']['pos_count'],
				percents[0]['U'], #100*(isp_counts_per_speed['0'][isp]['U']['pos_count'] / counts['0']['urban_pos_neg_count']),
				counts[25]['urban_pos_neg_count'],
				isp_counts_per_speed[25][isp]['U']['pos_count'],
				percents[25]['U'],#100*(isp_counts_per_speed['25'][isp]['U']['pos_count'] / counts['25']['urban_pos_neg_count']),

				# Pop info
				isp_counts_per_speed[0][isp]['pop']['total_pop']['U'],
				isp_counts_per_speed[0][isp]['pop']['covered_pop']['U'],
				100* (isp_counts_per_speed[0][isp]['pop']['covered_pop']['U']/isp_counts_per_speed[0][isp]['pop']['total_pop']['U']),
				isp_counts_per_speed[25][isp]['pop']['total_pop']['U'],
				isp_counts_per_speed[25][isp]['pop']['covered_pop']['U'],
				pop_25_percent['U'],#100* (isp_counts_per_speed[25][isp]['pop']['covered_pop']['U']/isp_counts_per_speed[25][isp]['pop']['total_pop']['U']),
			) + '\n' + \
			r"            & Rural &  {:,} & {:,} & {:.0f}\% & {:,} & {:,} & {:.0f}\% &  {:,} & {:,} & {:.0f}\% & {:,} & {:,} & {:.0f}\%  \\ ".format(
				counts[0]['rural_pos_neg_count'],
				isp_counts_per_speed[0][isp]['R']['pos_count'],
				percents[0]['R'],#100*(isp_counts_per_speed['0'][isp]['R']['pos_count'] / counts['0']['rural_pos_neg_count']),
				counts[25]['rural_pos_neg_count'],
				isp_counts_per_speed[25][isp]['R']['pos_count'],
				percents[25]['R'],#100*(isp_counts_per_speed['25'][isp]['R']['pos_count'] / counts['25']['rural_pos_neg_count']),

				# Pop info
				isp_counts_per_speed[0][isp]['pop']['total_pop']['R'],
				isp_counts_per_speed[0][isp]['pop']['covered_pop']['R'],
				100* (isp_counts_per_speed[0][isp]['pop']['covered_pop']['R']/isp_counts_per_speed[0][isp]['pop']['total_pop']['R']),
				isp_counts_per_speed[25][isp]['pop']['total_pop']['R'],
				isp_counts_per_speed[25][isp]['pop']['covered_pop']['R'],
				pop_25_percent['R'],#100* (isp_counts_per_speed[25][isp]['pop']['covered_pop']['R']/isp_counts_per_speed[25][isp]['pop']['total_pop']['R']),
			) + '\n' 

		# Adds to the latex output including unrecognized, excluded, and business addresses
		total_a = isp_counts_per_speed[0][isp]['U']['pos_count'] + isp_counts_per_speed[0][isp]['R']['pos_count'] + \
				isp_counts_per_speed[0][isp]['U']['neg_count'] + isp_counts_per_speed[0][isp]['R']['neg_count'] + \
				isp_counts_per_speed[0][isp]['U']['unrecognized_count'] + isp_counts_per_speed[0][isp]['R']['unrecognized_count'] + \
				isp_counts_per_speed[0][isp]['U']['business_count'] + isp_counts_per_speed[0][isp]['R']['business_count'] + \
				isp_counts_per_speed[0][isp]['U']['excluded_count'] + isp_counts_per_speed[0][isp]['R']['excluded_count']
		total_u = isp_counts_per_speed[0][isp]['U']['pos_count'] + \
				isp_counts_per_speed[0][isp]['U']['neg_count']+ \
				isp_counts_per_speed[0][isp]['U']['unrecognized_count']+ \
				isp_counts_per_speed[0][isp]['U']['business_count']+ \
				isp_counts_per_speed[0][isp]['U']['excluded_count']
		total_r = isp_counts_per_speed[0][isp]['R']['pos_count']+ \
				isp_counts_per_speed[0][isp]['R']['neg_count']+ \
				isp_counts_per_speed[0][isp]['R']['unrecognized_count']+ \
				isp_counts_per_speed[0][isp]['R']['business_count']+ \
				isp_counts_per_speed[0][isp]['R']['excluded_count']
		latex_output_full += \
			r"\rowcolor[HTML]{C0C0C0} " + '\n' + \
			r"{} & All & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  \\ ".format(
				isp_name,
				
				isp_counts_per_speed[0][isp]['U']['pos_count'] + isp_counts_per_speed[0][isp]['R']['pos_count'],
				100*((isp_counts_per_speed[0][isp]['U']['pos_count'] + isp_counts_per_speed[0][isp]['R']['pos_count'])/total_a),
				
				isp_counts_per_speed[0][isp]['U']['neg_count'] + isp_counts_per_speed[0][isp]['R']['neg_count'],
				100*((isp_counts_per_speed[0][isp]['U']['neg_count'] + isp_counts_per_speed[0][isp]['R']['neg_count'])/total_a),
				
				isp_counts_per_speed[0][isp]['U']['unrecognized_count'] + isp_counts_per_speed[0][isp]['R']['unrecognized_count'],
				100*((isp_counts_per_speed[0][isp]['U']['unrecognized_count'] + isp_counts_per_speed[0][isp]['R']['unrecognized_count'])/total_a),

				isp_counts_per_speed[0][isp]['U']['business_count'] + isp_counts_per_speed[0][isp]['R']['business_count'],
				100*((isp_counts_per_speed[0][isp]['U']['business_count'] + isp_counts_per_speed[0][isp]['R']['business_count'])/total_a),

				isp_counts_per_speed[0][isp]['U']['excluded_count'] + isp_counts_per_speed[0][isp]['R']['excluded_count'],
				100*((isp_counts_per_speed[0][isp]['U']['excluded_count'] + isp_counts_per_speed[0][isp]['R']['excluded_count'])/total_a),
	
			) + '\n' + \
			r"            & Urban  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  \\ ".format(
				isp_counts_per_speed[0][isp]['U']['pos_count'],
				100*(isp_counts_per_speed[0][isp]['U']['pos_count']/total_u),

				isp_counts_per_speed[0][isp]['U']['neg_count'], 
				100*(isp_counts_per_speed[0][isp]['U']['neg_count']/total_u),

				isp_counts_per_speed[0][isp]['U']['unrecognized_count'],
				100*(isp_counts_per_speed[0][isp]['U']['unrecognized_count']/total_u),

				isp_counts_per_speed[0][isp]['U']['business_count'],
				100*(isp_counts_per_speed[0][isp]['U']['business_count']/total_u),

				isp_counts_per_speed[0][isp]['U']['excluded_count'],
				100*(isp_counts_per_speed[0][isp]['U']['excluded_count']/total_u),
			) + '\n' + \
			r"            & Rural  & {:,} & {:.0f}\% & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  & {:,} & {:.0f}\%  \\ ".format(
				isp_counts_per_speed[0][isp]['R']['pos_count'],
				100*(isp_counts_per_speed[0][isp]['R']['pos_count']/total_r),

				isp_counts_per_speed[0][isp]['R']['neg_count'], 
				100*(isp_counts_per_speed[0][isp]['R']['neg_count']/total_r),

				isp_counts_per_speed[0][isp]['R']['unrecognized_count'],
				100*(isp_counts_per_speed[0][isp]['R']['unrecognized_count']/total_r),

				isp_counts_per_speed[0][isp]['R']['business_count'],
				100*(isp_counts_per_speed[0][isp]['R']['business_count']/total_r),

				isp_counts_per_speed[0][isp]['R']['excluded_count'],
				100*(isp_counts_per_speed[0][isp]['R']['excluded_count']/total_r),
			) + '\n' 

	# Calculate and print summary count row
	counts = dict()
	df_coverage_per_speed = pd.DataFrame(columns=['Average Coverage Across ISPs', 'Minimum Download Speed (Mbps)', 'Area Type'])
	for speed in speeds:
		counts[speed] = dict()
		counts[speed]['total_pos_neg_count'] = summary_count[speed]['U']['pos_count'] + summary_count[speed]['R']['pos_count'] +summary_count[speed]['U']['neg_count'] + summary_count[speed]['R']['neg_count']
		counts[speed]['urban_pos_neg_count'] = summary_count[speed]['U']['pos_count'] +summary_count[speed]['U']['neg_count'] 
		counts[speed]['rural_pos_neg_count'] = summary_count[speed]['R']['pos_count'] +summary_count[speed]['R']['neg_count'] 

		# FOR SPEED PLOT: Add values to dataframe to plot at different speeds
		if DOING_SPEED_PLOT:
			df_coverage_per_speed = df_coverage_per_speed.append([
					{
						'Average Coverage Across ISPs': 100*((summary_count[speed]['U']['pos_count'] + summary_count[speed]['R']['pos_count']) / counts[speed]['total_pos_neg_count']),
						'Minimum Download Speed (Mbps)': speed,
						'Area Type': 'Total',
					},
					{
						'Average Coverage Across ISPs': 100*(summary_count[speed]['U']['pos_count'] / counts[speed]['urban_pos_neg_count']),
						'Minimum Download Speed (Mbps)': speed,
						'Area Type': 'Urban',
					},
					{
						'Average Coverage Across ISPs':100*(summary_count[speed]['R']['pos_count'] / counts[speed]['rural_pos_neg_count']),
						'Minimum Download Speed (Mbps)': speed,
						'Area Type': 'Rural',
					}], ignore_index=True)


	latex_output += \
			r"\rowcolor[HTML]{C0C0C0} " + '\n'\
			r"Total & All &  --- & --- & {:.0f}\% & --- & ---& {:.0f}\% &  {:,}  & {:,}  & {:.0f}\% & {:,}  &{:,} &  {:.0f}\%  \\ ".format(
				#counts[0]['total_pos_neg_count'],
				#summary_count[0]['U']['pos_count'] + summary_count[0]['R']['pos_count'],
				100*((summary_count[0]['U']['pos_count'] + summary_count[0]['R']['pos_count']) / counts[0]['total_pos_neg_count']),
				#counts[25]['total_pos_neg_count'],
				#summary_count[25]['U']['pos_count'] + summary_count[25]['R']['pos_count'],
				100*((summary_count[25]['U']['pos_count'] + summary_count[25]['R']['pos_count']) / counts[25]['total_pos_neg_count']),

				# Pop
				summary_count[0]['pop']['total_pop']['total'],
				summary_count[0]['pop']['covered_pop']['total'],
				100 * (summary_count[0]['pop']['covered_pop']['total']/summary_count[0]['pop']['total_pop']['total']),
				summary_count[25]['pop']['total_pop']['total'],
				summary_count[25]['pop']['covered_pop']['total'],
				100 * (summary_count[25]['pop']['covered_pop']['total']/summary_count[25]['pop']['total_pop']['total']),
			) + '\n' + \
			r"            & Urban &  --- & --- & {:.0f}\% & --- & --- & {:.0f}\% &  {:,}  & {:,}  & {:.0f}\% & {:,}  &{:,} &  {:.0f}\% \\ ".format(
				#counts[0]['urban_pos_neg_count'],
				#summary_count[0]['U']['pos_count'],
				100*(summary_count[0]['U']['pos_count'] / counts[0]['urban_pos_neg_count']),
				#counts[25]['urban_pos_neg_count'],
				#summary_count[25]['U']['pos_count'],
				100*(summary_count[25]['U']['pos_count'] / counts[25]['urban_pos_neg_count']),

				# Pop
				summary_count[0]['pop']['total_pop']['U'],
				summary_count[0]['pop']['covered_pop']['U'],
				100 * (summary_count[0]['pop']['covered_pop']['U']/summary_count[0]['pop']['total_pop']['U']),
				summary_count[25]['pop']['total_pop']['U'],
				summary_count[25]['pop']['covered_pop']['U'],
				100 * (summary_count[25]['pop']['covered_pop']['U']/summary_count[25]['pop']['total_pop']['U']),
			) + '\n' + \
			r"            & Rural &  --- & --- & {:.0f}\% & --- & --- & {:.0f}\% &  {:,}  & {:,}  & {:.0f}\% & {:,}  &{:,} &  {:.0f}\% \\ ".format(
				#counts[0]['rural_pos_neg_count'],
				#summary_count[0]['R']['pos_count'],
				100*(summary_count[0]['R']['pos_count'] / counts[0]['rural_pos_neg_count']),
				#counts[25]['rural_pos_neg_count'],
				#summary_count[25]['R']['pos_count'],
				100*(summary_count[25]['R']['pos_count'] / counts[25]['rural_pos_neg_count']),

				# Pop
				summary_count[0]['pop']['total_pop']['R'],
				summary_count[0]['pop']['covered_pop']['R'],
				100 * (summary_count[0]['pop']['covered_pop']['R']/summary_count[0]['pop']['total_pop']['R']),
				summary_count[25]['pop']['total_pop']['R'],
				summary_count[25]['pop']['covered_pop']['R'],
				100 * (summary_count[25]['pop']['covered_pop']['R']/summary_count[25]['pop']['total_pop']['R']),
			) + '\n' 
	latex_output_full += \
			r"\rowcolor[HTML]{C0C0C0} " + '\n'\
			r"Total & All &  {:,} & {:,} & {:,} & {:,} & {:,} \\ ".format(
				summary_count[0]['U']['pos_count'] + summary_count[0]['R']['pos_count'],
				summary_count[0]['U']['neg_count'] + summary_count[0]['R']['neg_count'],
				summary_count[0]['U']['unrecognized_count'] + summary_count[0]['R']['unrecognized_count'],
				summary_count[0]['U']['business_count'] + summary_count[0]['R']['business_count'],
				summary_count[0]['U']['excluded_count'] + summary_count[0]['R']['excluded_count'],
			) + '\n' + \
			r"            & Urban &  {:,} & {:,} & {:,} & {:,} & {:,} \\ ".format(
				summary_count[0]['U']['pos_count'],
				summary_count[0]['U']['neg_count'],
				summary_count[0]['U']['unrecognized_count'],
				summary_count[0]['U']['business_count'],
				summary_count[0]['U']['excluded_count'],
			) + '\n' + \
			r"            & Rural &  {:,} & {:,} & {:,} & {:,} & {:,} \\ ".format(
				summary_count[0]['R']['pos_count'],
				summary_count[0]['R']['neg_count'],
				summary_count[0]['R']['unrecognized_count'],
				summary_count[0]['R']['business_count'],
				summary_count[0]['R']['excluded_count'],
			) + '\n' 


	pp.pprint(isp_counts_per_speed)
	pp.pprint(summary_count)
	print()
	print(latex_output)
	print()
	print(latex_output_full)


	# FOR SPEED PLOT: Plot the summary at different speeds
	if DOING_SPEED_PLOT:
		import matplotlib.ticker as mtick
		ax = sns.pointplot(x = 'Minimum Download Speed (Mbps)', y = 'Average Coverage Across ISPs', hue='Area Type', data = df_coverage_per_speed)
		ax.yaxis.set_major_formatter(mtick.PercentFormatter())

	plt.show() 

# --------------------------------------------------------------------------------------------------

def empty_blocks(state,speed):
	print('-------------------------STATE: {}-------------------------'.format(state))
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)
	state_results = dict()

	# Find completely empty blocks
	
	for isp in ISPS_PER_STATE[state]:
		print('---->ISP: {}'.format(isp))

		# Get all blocks that are covered according to FCC
		sql_statement = f"SELECT DISTINCT addr_census_block  \
							FROM addresses_{state} \
							WHERE {fcc_covered_non_local_sql(state,speed)}"

		sql_print(sql_statement)
		mycursor.execute(sql_statement)
		fcc_covered_block_count = len(mycursor.fetchall())

		# Get all empty blocks
		print('Getting empty blocks...')
		if isp == 'verizon':
			sql_statement = f"SELECT b.addr_census_block, b.cnt, b.10_responses,b.50_responses \
							FROM ( \
								SELECT addr_census_block, GROUP_CONCAT(a.tool_coverage_{isp}_10) as 10_responses , GROUP_CONCAT(a.tool_coverage_{isp}_50) as 50_responses, SUM(a.cnt) as cnt\
								FROM ( \
									SELECT addr_census_block, tool_coverage_{isp}_10, tool_coverage_{isp}_50, count(*) as cnt \
									FROM addresses_{state} \
									WHERE ({fcc_covers(isp=isp+'_10',speed=speed)} or {fcc_covers(isp=isp+'_50',speed=speed)}) AND {is_known_res()} \
									GROUP BY tool_coverage_{isp}_10, tool_coverage_{isp}_50, addr_census_block \
								) a \
								GROUP BY addr_census_block\
							)b \
							WHERE ((b.10_responses) LIKE '0' OR (b.10_responses) LIKE '21' OR (b.10_responses) LIKE ('0,21') OR (b.10_responses) LIKE ('21,0')) \
								AND ((b.50_responses) LIKE '0' OR (b.50_responses) LIKE '21' OR (b.50_responses) LIKE ('0,21') OR (b.50_responses) LIKE ('21,0'))"
		elif isp == 'att':

			sql_statement = f"SELECT b.addr_census_block, b.cnt, b.10_responses,b.50_responses,b.70_responses, b.ts \
							FROM ( \
								SELECT addr_census_block, GROUP_CONCAT(a.tool_coverage_{isp}_10) as 10_responses , GROUP_CONCAT(a.tool_coverage_{isp}_50) as 50_responses, GROUP_CONCAT(a.tool_coverage_{isp}_70) as 70_responses, SUM(a.cnt) as cnt, MAX(a.ts) AS ts\
								FROM ( \
									SELECT addr_census_block, tool_coverage_{isp}_10, tool_coverage_{isp}_50, tool_coverage_{isp}_70, count(*) as cnt, MAX(tool_timestamp_att_10) AS ts \
									FROM addresses_{state} \
									WHERE ({fcc_covers(isp=isp+'_10',speed=speed)} or {fcc_covers(isp=isp+'_50',speed=speed)}  or {fcc_covers(isp=isp+'_70',speed=speed)}) AND {is_known_res()} \
									GROUP BY tool_coverage_{isp}_10, tool_coverage_{isp}_50, tool_coverage_{isp}_70, addr_census_block \
								) a \
								GROUP BY addr_census_block\
							)b \
							WHERE ((b.10_responses) LIKE '0') \
								AND ((b.50_responses) LIKE '0') \
								AND ((b.70_responses) LIKE '0')"
		else:
			if state in ['AR','NC'] and isp == 'centurylink':
				fcc_coverage_where_clause = f"({fcc_covers(isp=isp+'_10',speed=speed)} or {fcc_covers(isp=isp+'_50',speed=speed)})"
			elif isp == 'windstream' and state == 'NC':
				fcc_coverage_where_clause = f"({fcc_covers(isp=isp+'_10',speed=speed)} or {fcc_covers(isp=isp+'_41',speed=speed)} or {fcc_covers(isp=isp+'_50',speed=speed)})"
			else:
				fcc_coverage_where_clause = f"{fcc_covers(isp=isp,speed=speed)}"
			sql_statement = f"SELECT b.addr_census_block, b.cnt, b.responses \
								FROM ( \
									/* Get string of all responses for the block */ \
									SELECT addr_census_block, GROUP_CONCAT(a.tool_coverage_{isp}) as responses, SUM(a.cnt) as cnt\
									FROM ( \
										SELECT addr_census_block, tool_coverage_{isp}, count(*) as cnt \
										FROM addresses_{state} \
										WHERE ({fcc_coverage_where_clause}) AND {is_known_res()} \
										GROUP BY tool_coverage_{isp}, addr_census_block \
									) a \
									GROUP BY addr_census_block\
								)b "
			if len(NEG_RESPONSES[isp]) == 2 and NULL in NEG_RESPONSES[isp]:
				sql_statement += f"WHERE (b.responses) LIKE '{NEG_RESPONSES[isp][0]}'"
			elif len(NEG_RESPONSES[isp]) == 2 and NULL not in NEG_RESPONSES[isp]:
				sql_statement += f"WHERE (b.responses) LIKE '{NEG_RESPONSES[isp][0]}' OR (b.responses) LIKE '{NEG_RESPONSES[isp][1]}' OR (b.responses) LIKE ('{NEG_RESPONSES[isp][0]},{NEG_RESPONSES[isp][1]}') OR (b.responses) LIKE ('{NEG_RESPONSES[isp][1]},{NEG_RESPONSES[isp][0]}')"
			else:
				raise Exception()

		#sql_print(sql_statement)
		mycursor.execute(sql_statement)
		empty_blocks = mycursor.fetchall()

		# Get address counts for all empty blocks
		print(f'# of empty blocks {len(empty_blocks)}')
		empty_block_counts = dict()
		empty_block_counts_large = dict()
		for empty_block_row in empty_blocks:
			#if random.randint(1,70) == 2:
			#	print(str(empty_block_row) + f' ({isp})')
			if isp == 'att':
				ts = empty_block_row[5]
				print(empty_block_row)
				if float(ts) > 1601251200:
					continue

			empty_block = empty_block_row[0]
			zero_response_count = empty_block_row[1]
			empty_block_counts[empty_block] = zero_response_count
			if zero_response_count > 20:
				empty_block_counts_large[empty_block] = zero_response_count
				#print(empty_block)

		state_results[isp] = dict()
		state_results[isp]['all_block_count'] = len(empty_block_counts)
		state_results[isp]['large_block_count'] = len(empty_block_counts_large)
		state_results[isp]['fcc_covered_block_count'] = fcc_covered_block_count
		pp.pprint(empty_block_counts_large)
		#state_results[isp]['all_blocks_counts'] = empty_block_counts
		state_results[isp]['large_blocks'] = empty_block_counts_large


		print('{} total blocks for {}'.format(len(empty_block_counts),isp))
		print('{} large blocks for {}'.format(len(empty_block_counts_large),isp))
		print('{} TOTAL blocks for {}'.format(state_results[isp]['fcc_covered_block_count'],isp))
	return state_results

# --------------------------------------------------------------------------------------------------

def excluded_blocks(state,speed):
	print('-------------------------STATE: {}-------------------------'.format(state))
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)
	state_results = dict()

	# Find completely empty blocks
	
	for isp in ISPS_PER_STATE[state]:
		print('---->ISP: {}'.format(isp))

		# Get all blocks that are covered according to FCC
		sql_statement = f"SELECT DISTINCT addr_census_block  \
							FROM addresses_{state} \
							WHERE {fcc_covered_non_local_sql(state,speed)}"

		sql_print(sql_statement)
		mycursor.execute(sql_statement)
		fcc_covered_block_count = len(mycursor.fetchall())

		# Get all empty blocks
		print('Getting empty blocks...')
		if isp == 'verizon':
			sql_statement = f"SELECT addr_census_block, GROUP_CONCAT(a.tool_coverage_{isp}_10) as 10_responses , GROUP_CONCAT(a.tool_coverage_{isp}_50) as 50_responses, SUM(a.cnt) as cnt\
							FROM ( \
								SELECT addr_census_block, tool_coverage_{isp}_10, tool_coverage_{isp}_50, count(*) as cnt \
								FROM addresses_{state} \
								WHERE ({fcc_covers(isp=isp+'_10',speed=speed)} or {fcc_covers(isp=isp+'_50',speed=speed)}) AND {is_known_res()} \
								GROUP BY tool_coverage_{isp}_10, tool_coverage_{isp}_50, addr_census_block \
							) a \
							GROUP BY addr_census_block "
		elif isp == 'att':
			sql_statement = f"SELECT addr_census_block, GROUP_CONCAT(a.tool_coverage_{isp}_10) as 10_responses , GROUP_CONCAT(a.tool_coverage_{isp}_50) as 50_responses, GROUP_CONCAT(a.tool_coverage_{isp}_70) as 70_responses, SUM(a.cnt) as cnt\
								FROM ( \
									SELECT addr_census_block, tool_coverage_{isp}_10, tool_coverage_{isp}_50, tool_coverage_{isp}_70, count(*) as cnt \
									FROM addresses_{state} \
									WHERE ({fcc_covers(isp=isp+'_10',speed=speed)} or {fcc_covers(isp=isp+'_50',speed=speed)}  or {fcc_covers(isp=isp+'_70',speed=speed)}) AND {is_known_res()} \
									GROUP BY tool_coverage_{isp}_10, tool_coverage_{isp}_50, tool_coverage_{isp}_70, addr_census_block \
								) a \
								GROUP BY addr_census_block"
		else:
			if state in ['AR','NC'] and isp == 'centurylink':
				fcc_coverage_where_clause = f"({fcc_covers(isp=isp+'_10',speed=speed)} or {fcc_covers(isp=isp+'_50',speed=speed)})"
			elif isp == 'windstream' and state == 'NC':
				fcc_coverage_where_clause = f"({fcc_covers(isp=isp+'_10',speed=speed)} or {fcc_covers(isp=isp+'_41',speed=speed)} or {fcc_covers(isp=isp+'_50',speed=speed)})"
			else:
				fcc_coverage_where_clause = f"{fcc_covers(isp=isp,speed=speed)}"
			sql_statement = f"/* Get string of all responses for the block */ \
								SELECT addr_census_block, GROUP_CONCAT(a.tool_coverage_{isp}) as responses, SUM(a.cnt) as cnt\
								FROM ( \
									SELECT addr_census_block, tool_coverage_{isp}, count(*) as cnt \
									FROM addresses_{state} \
									WHERE ({fcc_coverage_where_clause}) AND {is_known_res()} \
									GROUP BY tool_coverage_{isp}, addr_census_block \
								) a \
								GROUP BY addr_census_block "

		#sql_print(sql_statement)
		mycursor.execute(sql_statement)
		blocks = mycursor.fetchall()

		# Get address counts for all empty blocks
		excluded_blocks = dict()
		#empty_block_counts_large = dict()
		for block_row in blocks:

			block = block_row[0]
			responses = block_row[1].split(',')

			found_pos_or_neg = False
			for response in responses:
				if response in POS_RESPONSES[isp] or response in NEG_RESPONSES[isp]:
					found_pos_or_neg = True
			if found_pos_or_neg == False:
				excluded_blocks[block] = responses
		#pp.pprint(excluded_blocks)
						
		state_results[isp] = dict()
		state_results[isp]['excluded_block_count'] = len(excluded_blocks)
		state_results[isp]['fcc_covered_block_count'] = fcc_covered_block_count

		print('{} excluded blocks for {}'.format(len(excluded_blocks),isp))
		print('{} TOTAL blocks for {}'.format(state_results[isp]['fcc_covered_block_count'],isp))
	return state_results
# --------------------------------------------------------------------------------------------------

# Get list of empty blocks across all ISPs
def empty_blocks_total():
	all_block_counts_per_isp = {
		0: defaultdict(lambda: 0),
		25 :defaultdict(lambda: 0),
	}
	large_block_counts_per_isp = {
		0: defaultdict(lambda: 0),
		25 :defaultdict(lambda: 0),
	}
	total_fcc_block_counts_per_isp = {
		0: defaultdict(lambda: 0),
		25 :defaultdict(lambda: 0),
	}

	states = STATES
	speeds = [0]
	PRINT_VERIZON_ATT = True
	if PRINT_VERIZON_ATT == True:
		writers = dict()
		for isp in ['verizon','att']:
			outfile = open(f'OVERSTATED_BLOCKS_{isp}.csv', mode='w')
			outfile.seek(0)  
			outfile.truncate()
			writers[isp] = csv.writer(outfile, delimiter=',')
			writers[isp].writerow(['States with potentially overstated coverage'])
			writers[isp].writerow(['State', 'Census Block'])
		#large_blocks[speed][isp] = defaultdict(lambda:dict())
	
	for state in states:
		for speed in speeds:
			counts_state = empty_blocks(state,speed)
			print(state)
			print(speed)
			pp.pprint(counts_state)

			for isp, counts in counts_state.items():
				all_block_counts_per_isp[speed][isp] += counts['all_block_count']
				large_block_counts_per_isp[speed][isp] += counts['large_block_count']
				total_fcc_block_counts_per_isp[speed][isp] += counts['fcc_covered_block_count']
				if PRINT_VERIZON_ATT == True:
					#large_blocks[speed][isp].append(counts['large_blocks'])

					for block in counts['large_blocks']:
						writers[isp].writerow([state, block])

	pp.pprint(large_block_counts_per_isp)
	for isp in ALL_ISPS:
		print(r"{} & {:,} & {:,} & {:,} & {:,} \\".format(LABELS[isp], total_fcc_block_counts_per_isp[0][isp], large_block_counts_per_isp[0][isp], total_fcc_block_counts_per_isp[25][isp], large_block_counts_per_isp[25][isp]))
		


# --------------------------------------------------------------------------------------------------

def total_coverage_pop_fcc(state,method,speed):
	'''
		Gets total coverage population according to FCC
	'''
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	# Get population of each census block
	blocks_pop = get_census_block_population_counts(state, mycursor)

	# Get rural/urban classification for each block
	blocks_rural_classification = get_census_block_rural_classification(state,mycursor)
	#pp.pprint(blocks_rural_classification)

	# Get all blocks covered according to FCC
	sql_statement = "SELECT DISTINCT addr_census_block FROM addresses_{} WHERE ".format(state)
	sql_statement += fcc_covered_sql(state=state,method=method, speed=speed, limit_to_tool_blocks=True)
	sql_print(sql_statement)
	mycursor.execute(sql_statement)

	total_covered_count_urban = 0
	total_covered_count_rural = 0
	blocks = mycursor.fetchall()
	for block_row in blocks:
		#print(block_row)
		block = str(block_row[0])
		#if state == 'AR':
		#		block_rural_check = '0' + block
		#else:
		block_rural_check = block
		if blocks_rural_classification[block_rural_check] == 'U':
			total_covered_count_urban += blocks_pop[block]
		elif blocks_rural_classification[block_rural_check] == 'R':
			total_covered_count_rural += blocks_pop[block]
		else:
			raise Exception()
	
	return (total_covered_count_urban, total_covered_count_rural, blocks)

# --------------------------------------------------------------------------------------------------

# Get list of empty blocks across all ISPs
def excluded_blocks_total():
	all_block_counts_per_isp = {
		0: defaultdict(lambda: 0),
		25 :defaultdict(lambda: 0),
	}
	large_block_counts_per_isp = {
		0: defaultdict(lambda: 0),
		25 :defaultdict(lambda: 0),
	}
	total_fcc_block_counts_per_isp = {
		0: defaultdict(lambda: 0),
		25 :defaultdict(lambda: 0),
	}
	
	for state in ['VT']:
		for speed in [0,25]:
			counts_state = excluded_blocks(state,speed)
			print(state)
			print(speed)
			pp.pprint(counts_state)

			for isp, counts in counts_state.items():
				all_block_counts_per_isp[speed][isp] += counts['excluded_block_count']
				large_block_counts_per_isp[speed][isp] += counts['large_block_count']
				total_fcc_block_counts_per_isp[speed][isp] += counts['fcc_covered_block_count']


	pp.pprint(large_block_counts_per_isp)
	'''
	for isp in ALL_ISPS:
		print(r"{} & {:,} & {:,} & {:,} & {:,} \\".format(LABELS[isp], total_fcc_block_counts_per_isp[0][isp], large_block_counts_per_isp[0][isp], total_fcc_block_counts_per_isp[25][isp], large_block_counts_per_isp[25][isp]))
	'''


# --------------------------------------------------------------------------------------------------

def total_coverage_pop_fcc(state,method,speed):
	'''
		Gets total coverage population according to FCC
	'''
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	# Get population of each census block
	blocks_pop = get_census_block_population_counts(state, mycursor)

	# Get rural/urban classification for each block
	blocks_rural_classification = get_census_block_rural_classification(state,mycursor)
	#pp.pprint(blocks_rural_classification)

	# Get all blocks covered according to FCC
	sql_statement = "SELECT DISTINCT addr_census_block FROM addresses_{} WHERE ".format(state)
	sql_statement += fcc_covered_sql(state=state,method=method, speed=speed, limit_to_tool_blocks=True)
	sql_print(sql_statement)
	mycursor.execute(sql_statement)

	total_covered_count_urban = 0
	total_covered_count_rural = 0
	blocks = mycursor.fetchall()
	for block_row in blocks:
		#print(block_row)
		block = str(block_row[0])
		#if state == 'AR':
		#		block_rural_check = '0' + block
		#else:
		block_rural_check = block
		if blocks_rural_classification[block_rural_check] == 'U':
			total_covered_count_urban += blocks_pop[block]
		elif blocks_rural_classification[block_rural_check] == 'R':
			total_covered_count_rural += blocks_pop[block]
		else:
			raise Exception()
	
	return (total_covered_count_urban, total_covered_count_rural, blocks)

# --------------------------------------------------------------------------------------------------
def total_coverage_pop_tool(state,methods):
	'''
		Gets total coverage population according to our tool
		Check that all blocks returned from fcc calculations are in pos + neg calculations and if not need to assume those blocks have coverage
	'''
	print('-------------------------STATE: {}-------------------------'.format(state))
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	# Get population of each census block
	blocks_pop = get_census_block_population_counts(state, mycursor)
	print('Stored block population counts...')

	# Get rural/urban classification for each block
	blocks_rural_classification = get_census_block_rural_classification(state,mycursor)
	print('Stored block rural/urban data...')

	print()

	coverage_counts = dict()

	pos_count = {
		0: {
			'total': 0,
			'U': 0,
			'R': 0
		},
		25: {
			'total': 0,
			'U': 0,
			'R': 0
		},
	}
	all_count = {
		0: {
			'total': 0,
			'U': 0,
			'R': 0
		},
		25: {
			'total': 0,
			'U': 0,
			'R': 0
		},
	}

	for speed in ['0','25']:
		coverage_counts[speed] = dict()

		print('Speed: {}'.format(speed))
		for method in methods:
			print('Method: {}'.format(method))


			# Get total number of covered people according to FCC for specific method
			fcc_total_covered_count_urban, fcc_total_covered_count_rural, fcc_covered_blocks = total_coverage_pop_fcc(state=state, method=method,speed=speed)
			print('Calculated FCC total coverage count...')

			# Get negative count per block
			sql_statement=f"SELECT addr_census_block, count(*) \
							FROM (\
								SELECT * \
								FROM addresses_{state} \
								WHERE {fcc_covered_sql(state=state,limit_to_tool_blocks=False,speed=speed,method=method)} \
							) AS fcc_covered_addresses \
							WHERE {tool_not_covered_sql(state=state, method=method,speed=speed)}\
							GROUP BY addr_census_block \
							"
			#sql_print(sql_statement)
			mycursor.execute(sql_statement)
			block_not_covered_counts = dict()
			for block_count in mycursor.fetchall():
				block_not_covered_counts[block_count[0]] = block_count[1]

			print('Calculated negative counts per block. Number of blocks: {}'.format(len(block_not_covered_counts)))

			# Get positive count per block
			sql_statement=f"SELECT addr_census_block, count(*) \
							FROM (\
								SELECT * \
								FROM addresses_{state} \
								WHERE {fcc_covered_sql(state,limit_to_tool_blocks=False,speed=speed,method=method)} \
							) AS fcc_covered_addresses \
							WHERE {tool_covered_sql(state=state, speed=speed)}\
							GROUP BY addr_census_block \
							"
			mycursor.execute(sql_statement)
			block_covered_counts = dict()
			for block_count in mycursor.fetchall():
				block_covered_counts[block_count[0]] = block_count[1]

			print('Calculated positive counts per block. Number of blocks: {}'.format(len(block_covered_counts)))

			tool_total_covered_count_urban = 0
			tool_total_covered_count_rural = 0
			for block,covered_count in block_covered_counts.items(): #ERROR
				block = str(block)

				# Add to number of units covered 
				for area_type in ['total',blocks_rural_classification[block]]:
					pos_count[int(speed)][area_type] += covered_count
					if block in block_not_covered_counts:
						all_count[int(speed)][area_type] +=  covered_count + block_not_covered_counts[block]
					else:
						all_count[int(speed)][area_type] +=  covered_count

				block_rural_check = block
				if blocks_rural_classification[block_rural_check] == 'U':
					# Multiply population of block by ratio of covered to not covered unit count in the block and add to count
					if block in block_not_covered_counts:
						ratio = (covered_count / (covered_count + block_not_covered_counts[block]))
						tool_total_covered_count_urban +=  blocks_pop[block] * ratio
					# If the block isn't in the not covered block counts (i.e. every unit is covered), just add population of that block
					else:
						tool_total_covered_count_urban += blocks_pop[block]
				elif blocks_rural_classification[block_rural_check] == 'R':
					# Multiply population of block by ratio of covered to not covered unit count in the block and add to count
					if block in block_not_covered_counts:
						ratio = (covered_count / (covered_count + block_not_covered_counts[block]))
						tool_total_covered_count_rural +=  blocks_pop[block] * ratio
					# If the block isn't in the not covered block counts (i.e. every unit is covered), just add population of that block
					else:
						tool_total_covered_count_rural += blocks_pop[block]
				else:
					raise Exception()

			# ------------------
			# Test to make sure that the number of blocks in numerator and denominator are the same
			print('Number of FCC-covered blocks: {}'.format(len(fcc_covered_blocks)))
			tool_blocks = set(list(block_covered_counts.keys()) + list(block_not_covered_counts.keys()))
			print('Number of tool-returned blocks: {}'.format(len(tool_blocks)))

			fcc_only_blocks = list()
			for block_row in fcc_covered_blocks:
				block = block_row[0]
				if block not in tool_blocks:
					fcc_only_blocks.append(block)
			print('fcc only blocks: {}'.format(len(fcc_only_blocks)))
			missing_pop = 0
			for block in fcc_only_blocks:
				missing_pop += blocks_pop[block]
			print('missing pop: {}'.format(missing_pop))
			# ------------------

			print(f'State: {state}')
			print('URBAN:')
			print(f'FCC covered count: {fcc_total_covered_count_urban}')
			print(f'Tool covered count: {tool_total_covered_count_urban}')
			print(f'Covered %: {tool_total_covered_count_urban/fcc_total_covered_count_urban}')
			print('RURAL:')
			print(f'FCC covered count: {fcc_total_covered_count_rural}')
			print(f'Tool covered count: {tool_total_covered_count_rural}')
			print(f'Covered %: {tool_total_covered_count_rural/fcc_total_covered_count_rural}')
			print('TOTAL:')
			print(f'FCC covered count: {fcc_total_covered_count_urban+fcc_total_covered_count_rural}')
			print(f'Tool covered count: {tool_total_covered_count_urban+tool_total_covered_count_rural}')
			print(f'Covered %: {(tool_total_covered_count_urban+tool_total_covered_count_rural)/(fcc_total_covered_count_urban+fcc_total_covered_count_rural)}')
			print('------------')
			print()

			
			coverage_counts[speed][method] = {
				'block_covered_counts': block_covered_counts,
				'block_not_covered_counts' : block_not_covered_counts,
				'urban': {
					'fcc_total_covered_count': int(fcc_total_covered_count_urban),
					'tool_total_covered_count': int(tool_total_covered_count_urban),
					'tool_total_covered_percent': (tool_total_covered_count_urban/fcc_total_covered_count_urban),
				},
				'rural': {
					'fcc_total_covered_count': int(fcc_total_covered_count_rural),
					'tool_total_covered_count': int(tool_total_covered_count_rural),
					'tool_total_covered_percent': (tool_total_covered_count_rural/fcc_total_covered_count_rural),
				},
				'total': {
					'fcc_total_covered_count': int(fcc_total_covered_count_urban+fcc_total_covered_count_rural),
					'tool_total_covered_count': int(tool_total_covered_count_urban+tool_total_covered_count_rural),
					'tool_total_covered_percent': ((tool_total_covered_count_urban+tool_total_covered_count_rural)/(fcc_total_covered_count_urban+fcc_total_covered_count_rural)),
				},
				'count': {
					'pos_count':pos_count[int(speed)],
					'all_count': all_count[int(speed)],
				}
			}
	return coverage_counts
		



# --------------------------------------------------------------------------------------------------
'''
def total_coverage_pop_tool_list(state):
		#Gets total coverage population according to our tool
	print('-------------------------STATE: {}-------------------------'.format(state))
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	for method in [1,2]:
		print('Method: {}'.format(method))

		select_isp_fields_sql = "SELECT addr_full, addr_census_block"
		for isp in ISPS_PER_STATE[state]:
			if isp == 'verizon':
				select_isp_fields_sql += f", 'VERIZON', fcc_coverage_verizon_10, fcc_coverage_downspeed_verizon_10, tool_coverage_verizon_10, fcc_coverage_verizon_50, fcc_coverage_downspeed_verizon_50, tool_coverage_verizon_50"
			elif isp == 'att':
				select_isp_fields_sql += f", 'ATT', fcc_coverage_att_10, fcc_coverage_downspeed_att_10, tool_coverage_att_10, fcc_coverage_att_50, fcc_coverage_downspeed_att_50, tool_coverage_att_50, fcc_coverage_att_70, fcc_coverage_downspeed_att_70, tool_coverage_att_70"
			elif isp == 'centurylink' and state == 'AR':
				select_isp_fields_sql += f", 'CENTURYLINK', fcc_coverage_centurylink_10, fcc_coverage_downspeed_centurylink_10, ,fcc_coverage_centurylink_50, fcc_coverage_downspeed_centurylink_50, tool_coverage_centurylink"
			else:	
				select_isp_fields_sql += f", '{isp.upper()}', fcc_coverage_{isp}, fcc_coverage_downspeed_{isp}, tool_coverage_{isp}"

		# Get negative count per block
		sql_statement=f"{select_isp_fields_sql}  \
						FROM (\
							SELECT * \
							FROM addresses_{state} \
							WHERE {fcc_covered_sql(state)} \
						) AS fcc_covered_addresses \
						WHERE {tool_not_covered_sql(state, method)}\
						ORDER BY RAND() \
						LIMIT 100"
		print(select_isp_fields_sql)
		mycursor.execute(sql_statement)
		for row in mycursor.fetchall():
			print(row)
		
		# Get positive count per block
		sql_statement=f"{select_isp_fields_sql} \
						FROM (\
							SELECT * \
							FROM addresses_{state} \
							WHERE {fcc_covered_sql(state)} \
						) AS fcc_covered_addresses \
						WHERE {tool_covered_sql(state)}\
						ORDER BY RAND() \
						LIMIT 100"
		mycursor.execute(sql_statement)
		for row in mycursor.fetchall():
			print(row)
'''
# --------------------------------------------------------------------------------

ISP_SQL_INDEX = {
	'VT': {
		'consolidated': {
			'fcc': 1,
			'tool': 3,
		},
		'xfinity': {
			'fcc': 2,
			'tool': 4,
		},
	},
	'VA': {
		'xfinity': {
			'fcc': 1,
			'tool': 6,
		},
		'cox': {
			'fcc': 2,
			'tool': 7,
		},
		'verizon': {
			'fcc': (3,4),
			'tool': (8,9),
		},
		'centurylink': {
			'fcc': 5,
			'tool': 10,
		},
	},
	'AR': {
		'centurylink': {
			'fcc': (1,2),
			'tool': 9,
		},
		'att': {
			'fcc': (3,4,5),
			'tool': (10,11,12),
		},
		'xfinity': {
			'fcc': 6,
			'tool': 13,
		},
		'cox': {
			'fcc': 7,
			'tool': 14,
		},
		'windstream': {
			'fcc': 8,
			'tool': 15,
		},
	},
	'ME': {
		'consolidated' : {
			'fcc': (1),
			'tool': (3),
		},
		'charter': {
			'fcc' : (2),
			'tool': (4),
		},
	}, 
	'MA': {
		'verizon' : {
			'fcc': (1,2),
			'tool': (5,6),
		},
		'xfinity' : {
			'fcc': (3),
			'tool': (7),
		},
		'charter' : {
			'fcc': (4),
			'tool': (8),
		},
	},
	'NC': {
		'charter' : {
			'fcc': 1,
			'tool': 11,
		},
		'att' : {
			'fcc': (2,3,4),
			'tool': (12,13,14),
		},
		'centurylink' : {
			'fcc': (5,6),
			'tool': 15,
		},
		'frontier' : {
			'fcc': 7,
			'tool': 16,
		},
		'windstream' : {
			'fcc': (8,9,10),
			'tool': 17,
		}
	},
	'OH': {
		'att' : {
			'fcc': (1,2,3),
			'tool': (8,9,10),
		},
		'charter' : {
			'fcc': (4),
			'tool': (11),
		},
		'frontier' : {
			'fcc': (5),
			'tool': (12),
		},
		'centurylink' : {
			'fcc': (6),
			'tool': (13),
		},
		'windstream' : {
			'fcc': (7),
			'tool': (14),
		},
	},
	'WI' : {
		'att' : {
			'fcc': (1,2,3),
			'tool': (7,8,9),
		},
		'charter' : {
			'fcc': (4),
			'tool': (10),
		},
		'centurylink' : {
			'fcc': (5),
			'tool': (11),
		},
		'frontier' : {
			'fcc': (6),
			'tool': (12),
		},
	},
	'NY' : {
		'verizon' : {
			'fcc': (1,2),
			'tool': (5,6),
		},
		'charter' : {
			'fcc': (3),
			'tool': (7),
		},
		'frontier' : {
			'fcc': (4),
			'tool': (8),
		},
	}
}

def get_unit_competition_counts(row, state):
	unit_fcc_covered_count = 0
	unit_tool_covered_count = 0

	for isp in ISPS_PER_STATE[state]:
		if isp == 'verizon':
			if row[ISP_SQL_INDEX[state][isp]['fcc'][0]] == '1' or row[ISP_SQL_INDEX[state][isp]['fcc'][1]] == '1':
				unit_fcc_covered_count += 1

				if row[ISP_SQL_INDEX[state][isp]['tool'][0]] in POS_RESPONSES[isp] or row[ISP_SQL_INDEX[state][isp]['tool'][1]] in POS_RESPONSES[isp]:
					unit_tool_covered_count += 1
				elif row[ISP_SQL_INDEX[state][isp]['tool'][0]] in NEG_RESPONSES[isp] and row[ISP_SQL_INDEX[state][isp]['tool'][1]] in NEG_RESPONSES[isp]:
					pass
				else:
					#print('a')
					return (False, -1,-1)
			else:
				pass
		elif isp == 'att':
			if row[ISP_SQL_INDEX[state][isp]['fcc'][0]] == '1' or row[ISP_SQL_INDEX[state][isp]['fcc'][1]] == '1' or row[ISP_SQL_INDEX[state][isp]['fcc'][2]] == '1':
				unit_fcc_covered_count += 1

				if row[ISP_SQL_INDEX[state][isp]['tool'][0]] in POS_RESPONSES[isp] or row[ISP_SQL_INDEX[state][isp]['tool'][1]] in POS_RESPONSES[isp] or row[ISP_SQL_INDEX[state][isp]['tool'][2]] in POS_RESPONSES[isp]:
					unit_tool_covered_count += 1
				elif row[ISP_SQL_INDEX[state][isp]['tool'][0]] in NEG_RESPONSES[isp] and row[ISP_SQL_INDEX[state][isp]['tool'][1]] in NEG_RESPONSES[isp] and row[ISP_SQL_INDEX[state][isp]['tool'][2]] in NEG_RESPONSES[isp]:
					pass
				else:
					#print('b')
					return (False, -1,-1)
			else:
				pass

		elif isp == 'centurylink' and state in ['AR','NC']:
			if row[ISP_SQL_INDEX[state][isp]['fcc'][0]] == '1' or row[ISP_SQL_INDEX[state][isp]['fcc'][1]] == '1':
				unit_fcc_covered_count += 1

				if row[ISP_SQL_INDEX[state][isp]['tool']] in POS_RESPONSES[isp]:
					unit_tool_covered_count += 1
				elif row[ISP_SQL_INDEX[state][isp]['tool']] in NEG_RESPONSES[isp]:
					pass
				else:
					# We ignore counts for units where the tool couldn't get a result
					#print('c')
					return (False, -1,-1)
			else:
				pass
		elif isp == 'windstream' and state in ['NC']:
			if row[ISP_SQL_INDEX[state][isp]['fcc'][0]] == '1' or row[ISP_SQL_INDEX[state][isp]['fcc'][1]] == '1' or row[ISP_SQL_INDEX[state][isp]['fcc'][2]] == '1':
				unit_fcc_covered_count += 1

				if row[ISP_SQL_INDEX[state][isp]['tool']] in POS_RESPONSES[isp]:
					unit_tool_covered_count += 1
				elif row[ISP_SQL_INDEX[state][isp]['tool']] in NEG_RESPONSES[isp]:
					pass
				else:
					# We ignore counts for units where the tool couldn't get a result
					#print('c')
					return (False, -1,-1)
			else:
				pass
		
		else:
			if row[ISP_SQL_INDEX[state][isp]['fcc']] == '1':
				unit_fcc_covered_count += 1

				if row[ISP_SQL_INDEX[state][isp]['tool']] in POS_RESPONSES[isp]:
					unit_tool_covered_count += 1
				elif row[ISP_SQL_INDEX[state][isp]['tool']] in NEG_RESPONSES[isp]:
					pass
				else:
					# We ignore counts for units where the tool couldn't get a result
					'''
					print('d')
					print(state)
					print(isp)
					print(ISP_SQL_INDEX[state][isp]['tool'])
					print(row[ISP_SQL_INDEX[state][isp]['tool']])
					'''
					return (False, -1,-1)
			else:
				pass

	return True, unit_fcc_covered_count, unit_tool_covered_count


def competition(state, speed):
	# Connect to mysql database
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	sql_statement=f"SELECT addr_census_block, {fcc_select_fields(state)}, {tool_select_fields(state)}  \
					FROM addresses_{state} \
					WHERE {is_known_res()} AND {fcc_covered_non_local_sql(state=state, speed=speed)}"

	sql_print(sql_statement)
	mycursor.execute(sql_statement)


	block_fcc_covered_counts = defaultdict(lambda: list())
	total_fcc_covered_count = 0
	block_tool_covered_counts = defaultdict(lambda: list())
	total_tool_covered_count = 0
	num_units = 0

	for i, row in enumerate(mycursor.fetchall()):
		
		block = row[0]
		success, unit_fcc_covered_count, unit_tool_covered_count = get_unit_competition_counts(row, state)
		
		'''
		if i % 251 == 0:
			print(row)
			print('success: {}'.format(success))
			print('unit_fcc_covered_count: {}'.format(unit_fcc_covered_count))
			print('unit_tool_covered_count: {}'.format(unit_tool_covered_count))
			print()
		'''
		

		if success:
			block_fcc_covered_counts[block].append(unit_fcc_covered_count)
			block_tool_covered_counts[block].append(unit_tool_covered_count)
			total_fcc_covered_count += unit_fcc_covered_count
			total_tool_covered_count += unit_tool_covered_count
			num_units += 1

	print('Average fcc coverage: {}'.format(total_fcc_covered_count/num_units))
	print('Average tool coverage: {}'.format(total_tool_covered_count/num_units))

	#print(block_fcc_covered_counts)
	#print(block_tool_covered_counts)

	# Calculate averages per block
	avg_fcc_count_per_block = defaultdict(lambda: 0)
	avg_tool_count_per_block = defaultdict(lambda: 0)

	for block, counts in block_fcc_covered_counts.items():
		avg_fcc_count_per_block[block] = sum(counts)/len(counts)
	for block, counts in block_tool_covered_counts.items():
		avg_tool_count_per_block[block] = sum(counts)/len(counts)

	#print(avg_fcc_count_per_block)
	#print(avg_tool_count_per_block)

	return avg_fcc_count_per_block, avg_tool_count_per_block
		


# --------------------------------------------------------------------------------------------------

def competition_rural(state,speed):

	print('-------------------------STATE: {}-------------------------'.format(state))
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	# Get rural/urban classification for each block
	blocks_rural_classification = get_census_block_rural_classification(state,mycursor)
	print('Stored block rural/urban data...')

	# Get competition counts per block
	fcc_total_isp_avg_per_block, tool_total_isp_avg_per_block = competition(state,speed=speed)
	print('Calculated competition data...')

	# ---

	# 1) Average number of ISPs in each (urban) census block according to both FCC and Tool (dict)
	# 2) Total number of ISPs across all (urban) blocks according to both FCC and tool (int)
	fcc_urban_isp_avg_per_block = dict()
	fcc_urban_isp_avgs_sum = 0
	tool_urban_isp_avg_per_block = dict()
	tool_urban_isp_avgs_sum = 0

	# 1) Average number of ISPs in each (rural) census block according to both FCC and Tool (dict)
	# 2) Total number of ISPs across all (rural) blocks according to both FCC and tool (int)
	fcc_rural_isp_avg_per_block = dict()
	fcc_rural_isp_avgs_sum = 0
	tool_rural_isp_avg_per_block = dict()
	tool_rural_isp_avgs_sum = 0

	# 2) Total number of ISPs across all blocks according to both FCC and tool (int)
	fcc_total_isp_avgs_sum = 0
	tool_total_isp_avgs_sum = 0

	# Proportional overstatement per block
	urban_overstatement_per_block = dict()
	rural_overstatement_per_block = dict()


	for block, tool_isp_avg in tool_total_isp_avg_per_block.items():

		#if positive_count + negative_count > 30:

		if blocks_rural_classification[block] == 'U':
			fcc_urban_isp_avg_per_block[block] = fcc_total_isp_avg_per_block[block]
			fcc_urban_isp_avgs_sum += fcc_total_isp_avg_per_block[block]

			tool_urban_isp_avg_per_block[block] = tool_isp_avg
			tool_urban_isp_avgs_sum += tool_isp_avg

			urban_overstatement_per_block[block] = float(tool_isp_avg/fcc_total_isp_avg_per_block[block])		
		elif blocks_rural_classification[block] == 'R':
			fcc_rural_isp_avg_per_block[block] = fcc_total_isp_avg_per_block[block]
			fcc_rural_isp_avgs_sum += fcc_total_isp_avg_per_block[block]

			tool_rural_isp_avg_per_block[block] = tool_isp_avg
			tool_rural_isp_avgs_sum += tool_isp_avg

			rural_overstatement_per_block[block] = float(tool_isp_avg/fcc_total_isp_avg_per_block[block])
		else:
			raise Exception()

		fcc_total_isp_avgs_sum += fcc_total_isp_avg_per_block[block]
		tool_total_isp_avgs_sum += tool_isp_avg

	# Compute FCC average coverage stats
	fcc_urban_isp_avgs_avg = fcc_urban_isp_avgs_sum / len(fcc_urban_isp_avg_per_block)
	fcc_rural_isp_avgs_avg = fcc_rural_isp_avgs_sum / len(fcc_rural_isp_avg_per_block)
	fcc_total_isp_avgs_avg = fcc_total_isp_avgs_sum / len(fcc_total_isp_avg_per_block)

	# Compute tool average coverage stats 
	tool_urban_isp_avgs_avg = tool_urban_isp_avgs_sum / len(tool_urban_isp_avg_per_block)
	tool_rural_isp_avgs_avg = tool_rural_isp_avgs_sum / len(tool_rural_isp_avg_per_block)
	tool_total_isp_avgs_avg = tool_total_isp_avgs_sum / len(tool_total_isp_avg_per_block)

	# Store coverage data for the isp
	state_competition_data = {
		# int: Average competition across (urban/rural/total) blocks according to Tool
		'tool_urban_isp_avgs_avg': tool_urban_isp_avgs_avg,
		'tool_rural_isp_avgs_avg': tool_rural_isp_avgs_avg,
		'tool_total_isp_avgs_avg': tool_total_isp_avgs_avg,

		# int: Average competition across (urban/rural/total) blocks according to FCC
		'fcc_urban_isp_avgs_avg': fcc_urban_isp_avgs_avg,
		'fcc_rural_isp_avgs_avg': fcc_rural_isp_avgs_avg,
		'fcc_total_isp_avgs_avg': fcc_total_isp_avgs_avg,

		# dict: Average number of ISPs per (urban/rural/total) block according to Tool
		'tool_urban_isp_avg_per_block':tool_urban_isp_avg_per_block,
		'tool_rural_isp_avg_per_block':tool_rural_isp_avg_per_block,
		#'tool_total_isp_avg_per_block': tool_total_isp_avg_per_block, - commenting out just bc we don't actually use this value

		# dict: Average number of ISPs per (urban/rural/total) block according to FCC
		'fcc_urban_isp_avg_per_block': fcc_urban_isp_avg_per_block,
		'fcc_rural_isp_avg_per_block': fcc_rural_isp_avg_per_block,
		#'fcc_total_isp_avg_per_block': fcc_total_isp_avg_per_block, - commenting out just bc we don't actually use this value

		# dict: Proportional overstatement per (urban/rural) block
		'urban_overstatement_per_block': urban_overstatement_per_block,
		'rural_overstatement_per_block': rural_overstatement_per_block,


	}

	# First item is a list of averages in dict form for plotting with a df
	# Second item is a dict of all the data
	return state_competition_data


# --------------------------------------------------------------------------------------------------

def db_summary(state):
	'''
	Calculates db summary statistics
	'''
	print('-------------------------STATE: {}-------------------------'.format(state))
	# Connect to mysql database
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	# Calculate total number of houses
	mycursor.execute("SELECT count(*) FROM addresses_{} ".format(state))
	total_units_count = mycursor.fetchall()[0][0]

	print('Number of total household units in DB: {:,}'.format(total_units_count))

	# Calculate covered addresses according to FCC
	sql_statement = "SELECT count(*) FROM addresses_{} WHERE ( ".format(state)
	for i, isp in enumerate(ISPS_PER_STATE[state]):
		if i != 0:
			sql_statement += "OR "
		if isp == 'verizon' or (isp == 'centurylink' and state == 'AR'):
			sql_statement += "fcc_coverage_{}_10 = '1' OR fcc_coverage_{}_50 = '1' ".format(isp, isp)
		elif isp == 'att':
			sql_statement += "fcc_coverage_{}_10 = '1' OR fcc_coverage_{}_50 = '1' OR fcc_coverage_{}_70 = '1' ".format(isp, isp, isp)
		else:
			sql_statement += "fcc_coverage_{} = '1' ".format(isp)
	sql_statement += ') '
	mycursor.execute(sql_statement)
	fcc_covered_count = mycursor.fetchall()[0][0]

	print('Number of covered houses according to FCC: {:,} ({:.1f}%)'.format(fcc_covered_count, (fcc_covered_count/total_units_count)*100 ))

	# Calculate non-covered addresses according to FCC
	fcc_not_covered_count = total_units_count - fcc_covered_count

	print('Number of not-covered houses according to FCC: {:,} ({:.1f}%)'.format(fcc_not_covered_count, (fcc_not_covered_count/total_units_count)*100 ))

	# Calculate covered addresses with >= 25 mbps according to FCC
	sql_statement = "SELECT fcc_coverage_xfinity, fcc_coverage_downspeed_xfinity, fcc_coverage_centurylink, fcc_coverage_downspeed_centurylink, fcc_coverage_cox, fcc_coverage_downspeed_cox, fcc_coverage_verizon_10, fcc_coverage_downspeed_verizon_10, fcc_coverage_verizon_50, fcc_coverage_downspeed_verizon_50 FROM addresses_{} WHERE ( ".format(state)
	for i, isp in enumerate(ISPS_PER_STATE[state]):
		if i != 0:
			sql_statement += "OR "
		if isp == 'verizon' or (isp == 'centurylink' and state == 'AR'):
			sql_statement += "( (fcc_coverage_{}_10 = '1' OR fcc_coverage_{}_50 = '1') AND (fcc_coverage_downspeed_{}_10 >= 25 OR fcc_coverage_downspeed_{}_50 >= 25) ) ".format(isp, isp, isp, isp)
		elif isp == 'att':
			sql_statement += "( (fcc_coverage_{}_10 = '1' OR fcc_coverage_{}_50 = '1' OR fcc_coverage_{}_70 = '1') AND (fcc_coverage_downspeed_{}_10 >= 25 OR fcc_coverage_downspeed_{}_50 >= 25 OR fcc_coverage_downspeed_{}_70 >= 25) ) ".format(isp, isp, isp, isp, isp, isp)
		else:
			sql_statement += "(fcc_coverage_{} = '1' AND fcc_coverage_downspeed_{} >= 25)".format(isp, isp)
	sql_statement += ') LIMIT 100'
	mycursor.execute(sql_statement)
	#fcc_covered_speed_count = mycursor.fetchall()[0][0]
	for row in mycursor.fetchall():
		print(row)

	print('Number of sufficiently covered (>= 25 mpbs) houses according to FCC: {:,} ({:.1f}%)'.format(fcc_covered_speed_count, (fcc_covered_speed_count/total_units_count)*100 ))

	# Calculate non-covered addresses according to FCC
	fcc_not_covered_speed_count = total_units_count - fcc_covered_speed_count

	print('Number of insufficiently covered (>= 25 mpbs) houses according to FCC: {:,} ({:.1f}%)'.format(fcc_not_covered_speed_count, (fcc_not_covered_speed_count/total_units_count)*100 ))

# --------------------------------------------------------------------------------------------------

def latex_total_coverage_pop_tool_db():
	# TABLE 6.1: estimates of populations based on our db
	coverage_counts = dict()
	for state in ['VT']: 
		coverage_counts[state] = total_coverage_pop_tool(state)
	
	'''
	coverage_counts[method] = {
			'block_covered_counts': block_covered_counts,
			'block_not_covered_counts' : block_not_covered_counts,
			'urban': {
				'fcc_total_covered_count': fcc_total_covered_count_urban,
				'tool_total_covered_count': tool_total_covered_count_urban,
				'tool_total_covered_percent': tool_total_covered_count_urban/fcc_total_covered_count_urban,
			},
			'rural': {
				'fcc_total_covered_count': fcc_total_covered_count_rural,
				'tool_total_covered_count': tool_total_covered_count_rural,
				'tool_total_covered_percent': tool_total_covered_count_rural/fcc_total_covered_count_rural,
			},
			'total': {
				'fcc_total_covered_count': fcc_total_covered_count_urban+fcc_total_covered_count_rural,
				'tool_total_covered_count': tool_total_covered_count_urban+tool_total_covered_count_rural,
				'tool_total_covered_percent': (tool_total_covered_count_urban+tool_total_covered_count_rural)/(fcc_total_covered_count_urban+fcc_total_covered_count_rural),
			},
		}
	'''
	# TABLE 6.1
	latex_table = ''
	for state, coverage_data in coverage_counts.items():
		# Return latex table text 
		latex_table += "%---------------------------------------\n"
		latex_table += r"\rowcolor[HTML]{74DFE5}  " + \
						r'\cellcolor[HTML]{68CBD0}                                    & \multicolumn{1}{l|}{\cellcolor[HTML]{74DFE5}All}                & '  + "{:,}".format(coverage_data[1]['total']['fcc_total_covered_count']) + r'                       & '  + "{:,}".format(coverage_data[1]['total']['tool_total_covered_count']) + r'                       & '  + "{:.2f}".format(coverage_data[1]['total']['tool_total_covered_percent']) + r'\%       & '  + "{:,}".format(coverage_data[2]['total']['tool_total_covered_count']) + r'                       & '  + "{:.2f}".format(coverage_data[2]['total']['tool_total_covered_percent']) + r'\%       \\ \cline{2-7}' + \
						r"\cellcolor[HTML]{68CBD0}                                    & Urban                                                           & "  + "{:,}".format(coverage_data[1]['urban']['fcc_total_covered_count']) + r"                       & "  + "{:,}".format(coverage_data[1]['urban']['tool_total_covered_count']) + r"                       & "  + "{:.2f}".format(coverage_data[1]['urban']['tool_total_covered_percent']) + r"\%       & "  + "{:,}".format(coverage_data[2]['urban']['tool_total_covered_count']) + r"                       & "  + "{:.2f}".format(coverage_data[2]['urban']['tool_total_covered_percent']) + r"\%       \\ \cline{2-7}" + \
						r"\multirow{-3}{*}{\cellcolor[HTML]{68CBD0}\textit{" + LABELS[state] + r"}} & Rural                                                           & "  + "{:,}".format(coverage_data[1]['rural']['fcc_total_covered_count']) + r"                       & "  + "{:,}".format(coverage_data[1]['rural']['tool_total_covered_count']) + r"                       & "  + "{:.2f}".format(coverage_data[1]['rural']['tool_total_covered_percent']) + r"\%       & "  + "{:,}".format(coverage_data[2]['rural']['tool_total_covered_count']) + r"                       & " + "{:.2f}".format(coverage_data[2]['rural']['tool_total_covered_percent']) + r"\%       \\ \hline" + '\n' 
		latex_table += "%---------------------------------------\n"
	print(latex_table)

def latex_total_coverage_pop_tool_real():

	# TABLE 6.2
	# Get full population estimates using our db results with FCC numbers:
	print('-------------- FULL POPULATION ESTIMATE -------------')
	coverage_counts = dict()
	for state in ['VA']: 
		coverage_counts[state] = total_coverage_pop_tool(state)

	FCC_POP_COVERED = {
		'VA': {
			'total': (7772000, 91.7),
			'urban' : (6231000, 97.4),
			'rural': (1541000, 74.1),
			'EVAL_POP_total': 8475000,
			'EVAL_POP_urban': 6397000,
			'EVAL_POP_rural': 2078000,
		},
		'VT': {
			'total': (557000, 89.3),
			'urban' : (237000, 98.7),
			'rural': (320000, 83.4),
			'EVAL_POP_total': 624000,
			'EVAL_POP_urban': 241000,
			'EVAL_POP_rural': 383000,

		},
		'AR': {
			'total': (2324000, 77.4),
			'urban' : (1580000, 94.4),
			'rural': (745000, 55.9),
			'EVAL_POP_total': 3004000,
			'EVAL_POP_urban': 1673000,
			'EVAL_POP_rural': 1331000,
		},
	}

	latex_table = ''
	real_pops_covered_per_state = dict()
	for state, coverage_count in coverage_counts.items():
		pops_covered = dict()
		for speed in ['0','25']:
			pops_covered[speed] = dict()
			for method in [2]:
				print('---METHOD: {}---'.format(method))
				pops_covered[speed][method] = dict()

				for type_blocks in ['total','urban','rural']:
					print(type_blocks)
					print('PCT: {}'.format(coverage_count[speed][method][type_blocks]['tool_total_covered_percent']))
					pops_covered[speed][method][type_blocks] = (
						coverage_count[speed][method][type_blocks]['tool_total_covered_percent'] * FCC_POP_COVERED[state][type_blocks][0],
						coverage_count[speed][method][type_blocks]['tool_total_covered_percent'] * FCC_POP_COVERED[state][type_blocks][1],
					)
		
		pp.pprint(pops_covered)
		continue
		real_pops_covered_per_state[state] = pops_covered 	

		latex_table += '%------------------------------\n'
		latex_table += r"\rowcolor[HTML]{74DFE5} " + \
						r"\cellcolor[HTML]{68CBD0}                                    & \multicolumn{1}{l|}{\cellcolor[HTML]{74DFE5}All}                & " + "{:,}".format(FCC_POP_COVERED[state]['total'][0]) + r"                    & " + "{:.2f}".format(FCC_POP_COVERED[state]['total'][1]) + r"       & " + "{:,}".format(int(pops_covered[2]['total'][0])) + r"                             & " + "{:.2f}".format(pops_covered[2]['total'][1]) + r"\%       \\ \cline{2-8} " + \
						r"\cellcolor[HTML]{68CBD0}                                    & Urban                                                           & " + "{:,}".format(FCC_POP_COVERED[state]['urban'][0]) + r"                    & " + "{:.2f}".format(FCC_POP_COVERED[state]['urban'][1]) + r"       & " + "{:,}".format(int(pops_covered[2]['urban'][0])) + r"                             & " + "{:.2f}".format(pops_covered[2]['urban'][1]) + r"\%       \\ \cline{2-8}" + \
						r"\multirow{-3}{*}{\cellcolor[HTML]{68CBD0}\textit{" + LABELS[state] + r"}}  & Rural                                                           & " + "{:,}".format(FCC_POP_COVERED[state]['rural'][0]) + r"                    & " + "{:.2f}".format(FCC_POP_COVERED[state]['rural'][1]) + r"       & " + "{:,}".format(int(pops_covered[2]['rural'][0])) + r"                             & " + "{:.2f}".format(pops_covered[2]['rural'][1]) + r"\%       \\ \hline" + '\n'
		latex_table += '%------------------------------\n'
	latex_table += '%------------------------------\n'
	exit()
	# Fixed it up to here with different speeds, until I realized there aren't FCC stats for anything other than >= 25 mbps

	### Get national numbers

	# Get FCC's national eval counts 
	EVAL_POPS_NATIONAL = dict()
	for block_type in ['total','urban','rural']:
		EVAL_POP_NATIONAL = 0
		for state in STATES: 
			EVAL_POP_NATIONAL += FCC_POP_COVERED[state][f'EVAL_POP_{block_type}']
		EVAL_POPS_NATIONAL[block_type] = EVAL_POP_NATIONAL

	pp.pprint(real_pops_covered_per_state)
	pp.pprint(EVAL_POPS_NATIONAL)

	'''
	fcc: { 'rural': (1447522.4295457527, 69.60506945447129),
	       'total': (7466733.041124668, 88.09822695202419),
	       'urban': (6019503.98805291, 94.09399589734448)},

	1: {   'rural': (1447522.4295457527, 69.60506945447129),
	       'total': (7466733.041124668, 88.09822695202419),
	       'urban': (6019503.98805291, 94.09399589734448)},

	2: {   'rural': (1454602.2169323715, 69.94550569415232),
	       'total': (7502536.008563722, 88.52065774386172),
	       'urban': (6048227.337957032, 94.54298551067484)}}
	  '''
	coverages_national = {
		'fcc': dict(),
		1: dict(),
		2: dict(),
	}

	# Get total FCC counts
	for block_type in ['total','urban','rural']:
		covered_count = 0
		for state in STATES:
			covered_count += FCC_POP_COVERED[state][block_type][0]
		covered_pct = (covered_count / EVAL_POPS_NATIONAL[block_type]) * 100.0
		coverages_national['fcc'][block_type] = (covered_count,covered_pct)
	# Get total for methods 1/2
	for method in [2]:
		for block_type in ['total','urban','rural']:
			national_covered_count = 0
			for state in STATES:
				national_covered_count += real_pops_covered_per_state[state][method][block_type][0]
			national_covered_pct = (national_covered_count / EVAL_POPS_NATIONAL[block_type]) * 100.0
			coverages_national[method][block_type] = (national_covered_count,national_covered_pct)
	print('COVERAGES NATIONAL:')
	pp.pprint(coverages_national)

	#print the results for all
	latex_table1 += '%------------------------------\n'
	latex_table1 += '%------------------------------\n'
	latex_table1 += r"\rowcolor[HTML]{74DFE5} " + \
					r"\cellcolor[HTML]{68CBD0}                                    & \multicolumn{1}{l|}{\cellcolor[HTML]{74DFE5}\textbf{All}}                & " + "{:,}".format(coverages_national['fcc']['total'][0]) + r"                    & " + "{:.2f}".format(coverages_national['fcc']['total'][1]) + r"\%       & " + "{:,}".format(int(coverages_national[1]['total'][0])) + r"                             & " + "{:.2f}".format(coverages_national[1]['total'][1]) + r"\%       & " + "{:,}".format(int(coverages_national[2]['total'][0])) + r"                             & " + "{:.2f}".format(coverages_national[2]['total'][1]) + r"\%       \\ \cline{2-8} " + \
					r"\cellcolor[HTML]{68CBD0}                                    & \textbf{Urban}                                                           & " + "{:,}".format(coverages_national['fcc']['urban'][0]) + r"                    & " + "{:.2f}".format(coverages_national['fcc']['urban'][1]) + r"\%       & " + "{:,}".format(int(coverages_national[1]['urban'][0])) + r"                             & " + "{:.2f}".format(coverages_national[1]['urban'][1]) + r"\%       & " + "{:,}".format(int(coverages_national[2]['urban'][0])) + r"                             & " + "{:.2f}".format(coverages_national[2]['urban'][1]) + r"\%       \\ \cline{2-8}" + \
					r"\multirow{-3}{*}{\cellcolor[HTML]{68CBD0}\textit{\textbf{Total}}}  & \textbf{Rural}                                                           & " + "{:,}".format(coverages_national['fcc']['rural'][0]) + r"                    & " + "{:.2f}".format(coverages_national['fcc']['rural'][1]) + r"\%       & " + "{:,}".format(int(coverages_national[1]['rural'][0])) + r"                             & " + "{:.2f}".format(coverages_national[1]['rural'][1]) + r"\%       & " + "{:,}".format(int(coverages_national[2]['rural'][0])) + r"                             & " + "{:.2f}".format(coverages_national[2]['rural'][1]) + r"\%       \\ \hline" + '\n'
	latex_table1 += '%------------------------------\n'
	print(latex_table1)

	print('LATEX TABLE 2 (WITHOUT METHOD 1)')
	#print the results for all
	latex_table2 += '%------------------------------\n'
	latex_table2 += '%------------------------------\n'
	latex_table2 += r"\rowcolor[HTML]{74DFE5} " + \
					r"\cellcolor[HTML]{68CBD0}                                    & \multicolumn{1}{l|}{\cellcolor[HTML]{74DFE5}\textbf{All}}                & " + "{:,}".format(coverages_national['fcc']['total'][0]) + r"                    & " + "{:.2f}".format(coverages_national['fcc']['total'][1]) + r"       & " + "{:,}".format(int(coverages_national[2]['total'][0])) + r"                             & " + "{:.2f}".format(coverages_national[2]['total'][1]) + r"\%       \\ \cline{2-8} " + \
					r"\cellcolor[HTML]{68CBD0}                                    & \textbf{Urban}                                                           & " + "{:,}".format(coverages_national['fcc']['urban'][0]) + r"                    & " + "{:.2f}".format(coverages_national['fcc']['urban'][1]) + r"       & " + "{:,}".format(int(coverages_national[2]['urban'][0])) + r"                             & " + "{:.2f}".format(coverages_national[2]['urban'][1]) + r"\%       \\ \cline{2-8}" + \
					r"\multirow{-3}{*}{\cellcolor[HTML]{68CBD0}\textit{\textbf{Total}}}  & \textbf{Rural}                                                           & " + "{:,}".format(coverages_national['fcc']['rural'][0]) + r"                    & " + "{:.2f}".format(coverages_national['fcc']['rural'][1]) + r"       & " + "{:,}".format(int(coverages_national[2]['rural'][0])) + r"                             & " + "{:.2f}".format(coverages_national[2]['rural'][1]) + r"\%       \\ \hline" + '\n'
	latex_table2 += '%------------------------------\n'
	print(latex_table2)


# --------------------------------------------------------------------------------------------------
def local_coverage():
	summary_counts = {
		'0': {'local_count':0,'total_count':0, 'local_unit_count':0,'total_unit_count':0},
		'25': {'local_count':0,'total_count':0, 'local_unit_count':0,'total_unit_count':0}
	}
	for state in STATES:
		#print('-------------------------STATE: {}-------------------------'.format(state))
		# Connect to mysql database
		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		blocks_pop = get_census_block_population_counts(state, mycursor)
		local_coverage_per_speed = dict()
		local_unit_count = {
			'0':0,'25':0,
		}
		total_unit_count = {
			'0':0,'25':0,
		}

		for speed in ['0','25']:
			# Local covered blocks
			if state == 'NY':
				sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE {is_known_res()}  AND fcc_coverage_LOCAL_altice = '1' and fcc_coverage_downspeed_LOCAL_altice >= {speed}"
			else:
				sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE {is_known_res()}  AND fcc_coverage_LOCAL = '1' and fcc_coverage_downspeed_LOCAL >= {speed}"
			mycursor.execute(sql_statement)

			local_count = 0
			for i, row in enumerate(mycursor.fetchall()):
				block = row[0]
				#if state == 'AR':
				#	block = block[1:]

				local_count += blocks_pop[block]

			# Local covered units
			if state == 'NY':
				sql_statement = f"SELECT count(*) from addresses_{state} WHERE {is_known_res()} AND fcc_coverage_LOCAL_altice = '1' and fcc_coverage_downspeed_LOCAL_altice >= {speed}"
			else:
				sql_statement = f"SELECT count(*) addr_census_block from addresses_{state} WHERE {is_known_res()} AND fcc_coverage_LOCAL = '1' and fcc_coverage_downspeed_LOCAL >= {speed}"
			mycursor.execute(sql_statement)
			local_unit_count[speed] =  mycursor.fetchall()[0][0]
			summary_counts[speed]['local_unit_count'] += local_unit_count[speed]

			# All covered units
			sql_statement = f"SELECT count(*) from addresses_{state} WHERE {is_known_res()} AND ({fcc_covered_sql(state=state,limit_to_tool_blocks=False,speed=speed)})"
			mycursor.execute(sql_statement)
			total_unit_count[speed] = mycursor.fetchall()[0][0]
			summary_counts[speed]['total_unit_count'] += total_unit_count[speed]

			# All blocks
			sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE {is_known_res()} AND ({fcc_covered_sql(state=state,limit_to_tool_blocks=False,speed=speed)})"
			mycursor.execute(sql_statement)
			total_count = 0
			for i, row in enumerate(mycursor.fetchall()):
				block = row[0]
				#if state == 'AR':
				#	block = block[1:]

				total_count += blocks_pop[block]
			local_coverage_per_speed[speed] = local_count/total_count
			summary_counts[speed]['local_count'] += local_count
			summary_counts[speed]['total_count'] += total_count
			'''
			print(f'----STATE: {state}')
			print(f'Pop served by local ISPs: {local_count}')
			print(f'Percent: {local_count/total_count}%)')
			print(f'Total pop: {total_count}')
			'''
		print(r"{} & {:.2f}\% & {:.2f}\% {:.2f}\% & {:.2f}\% \\".format(
				LABELS[state],
				100*local_unit_count['0']/total_unit_count['0'],
				100*local_unit_count['25']/total_unit_count['25'],
				local_coverage_per_speed['0']*100,
				local_coverage_per_speed['25']*100,
			)
		)
	print(r"Total & {:.2f}\% & {:.2f}\% & {:.2f}\% & {:.2f}\% \\".format(
		100*(summary_counts['0']['local_unit_count']/summary_counts['0']['total_unit_count']),
		100*(summary_counts['25']['local_unit_count']/summary_counts['25']['total_unit_count']),
		(summary_counts['0']['local_count']/summary_counts['0']['total_count'])*100,(summary_counts['25']['local_count']/summary_counts['25']['total_count'])*100
		)
	)

# --------------------------------------------------------------------------------------------------
def major_coverage():
	for state in STATES:
		#print('-------------------------STATE: {}-------------------------'.format(state))
		# Connect to mysql database
		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		blocks_pop = get_census_block_population_counts(state, mycursor)
		local_coverage_per_speed = dict()

		summary_counts = {
			'0': {'major_count':0,'total_count':0},
			'25': {'major_count':0,'total_count':0}
		}

		for speed in ['0','25']:
			# major ISP covered blocks
			sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE {fcc_covered_non_local_sql(state=state, speed=speed)}"
			# sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE fcc_coverage_LOCAL = '1' and fcc_coverage_downspeed_LOCAL >= {speed}"
			mycursor.execute(sql_statement)

			major_count = 0
			for i, row in enumerate(mycursor.fetchall()):
				block = row[0]
				#if state == 'AR':
				#	block = block[1:]

				major_count += blocks_pop[block]

			# All blocks
			sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE ({fcc_covered_sql(state=state,limit_to_tool_blocks=False,speed=speed)})"
			mycursor.execute(sql_statement)


			total_count = 0
			for i, row in enumerate(mycursor.fetchall()):
				block = row[0]
				#if state == 'AR':
				#	block = block[1:]

				total_count += blocks_pop[block]
			local_coverage_per_speed[speed] = major_count/total_count
			summary_counts[speed]['major_count'] += major_count
			summary_counts[speed]['total_count'] += total_count
			

			if False:
				print(f'----STATE: {state}')
				print(f'Pop served by major ISPs: {major_count}')
				print(f'Percent: {major_count/total_count}%)')
				print(f'Total pop: {total_count}')

		print(r"{} & {:.2f}\% & {:.2f}\% \\".format(LABELS[state], local_coverage_per_speed['0'],local_coverage_per_speed['25']))
	print(r"Total & {:.2f}\% & {:.2f}\% \\".format((100*(summary_counts['0']['major_count']/summary_counts['0']['total_count'])),(100*(summary_counts['25']['major_count']/summary_counts['25']['total_count']))))


# --------------------------------------------------------------------------------------------------
def coverage_per_major_isp():
	counts = dict()
	for state in STATES:
		print('STATE: {}'.format(state))
		#print('-------------------------STATE: {}-------------------------'.format(state))
		# Connect to mysql database
		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		blocks_pop = get_census_block_population_counts(state, mycursor)
		
		counts[state] = dict()


		for speed in ['0']:
			counts[state][speed] = dict()

			sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE ({fcc_covered_sql(state=state,limit_to_tool_blocks=False,speed=speed)})"
			mycursor.execute(sql_statement)

			total_count = 0
			for i, row in enumerate(mycursor.fetchall()):
				block = row[0]
				#if state == 'AR':
				#	block = block[1:]

				total_count += blocks_pop[block]
			counts[state][speed]['total'] = total_count

			for isp in ISPS_PER_STATE[state]:

				# Get WHERE clause
				if isp == 'verizon' or (isp == 'centurylink' and state in ['AR','NC']):
					sql_statement = f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_50 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed})) "
				elif isp == 'att':
					sql_statement = f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_50 = '1' OR fcc_coverage_{isp}_70 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed} OR fcc_coverage_downspeed_{isp}_70 >= {speed} )) "
				elif isp == 'windstream' and state == 'NC':
					sql_statement = f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_41 = '1' OR fcc_coverage_{isp}_50 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_41 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed} )) "
				else:
					sql_statement = f"(fcc_coverage_{isp} = '1' AND fcc_coverage_downspeed_{isp} >= {speed}) "

				sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE {sql_statement}"

				mycursor.execute(sql_statement)

				isp_count = 0
				for i, row in enumerate(mycursor.fetchall()):
					block = row[0]
					#if state == 'AR':
					#	block = block[1:]

					isp_count += blocks_pop[block]
				counts[state][speed][isp] = isp_count
				print('{}: {:.2f}'.format(isp,float(counts[state][speed][isp]/counts[state][speed]['total'])))
	pp.pprint(counts)

# --------------------------------------------------------------------------------------------------

def pop_per_state():
	total = 0
	for state in STATES:
		# Connect to mysql database
		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		mycursor.execute(f"SELECT addr_id from addresses_{state} order by -addr_id limit 1")
		count  = int(mycursor.fetchall()[0][0])
		total += count
		print(f"{state}: {count}")
	print(total)

# --------------------------------------------------------------------------------------------------

# Get the ISPs for each block in state >= speed
# Returns dict{ block : isps in that block (set) }
def get_isps_per_block(state, speed):
	#print(state)
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	isps_per_block = defaultdict(lambda:set())

	for isp in ISPS_PER_STATE[state]:
		if isp == 'verizon' or (isp == 'centurylink' and state in ['AR','NC']):
			sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE (fcc_coverage_{isp}_10 = '1' AND fcc_coverage_downspeed_{isp}_10 >= {speed}) OR (fcc_coverage_{isp}_50 = '1' AND fcc_coverage_downspeed_{isp}_50 >= {speed})"
		elif isp == 'att':
			sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE (fcc_coverage_{isp}_10 = '1' AND fcc_coverage_downspeed_{isp}_10 >= {speed}) OR (fcc_coverage_{isp}_50 = '1' AND fcc_coverage_downspeed_{isp}_50 >= {speed}) OR (fcc_coverage_{isp}_70 = '1' AND fcc_coverage_downspeed_{isp}_70 >= {speed})"
		elif isp == 'windstream' and state == 'NC':
			sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE (fcc_coverage_{isp}_10 = '1' AND fcc_coverage_downspeed_{isp}_10 >= {speed}) OR (fcc_coverage_{isp}_41 = '1' AND fcc_coverage_downspeed_{isp}_41 >= {speed}) OR (fcc_coverage_{isp}_50 = '1' AND fcc_coverage_downspeed_{isp}_50 >= {speed})"
		else:
			sql_statement = f"SELECT DISTINCT addr_census_block from addresses_{state} WHERE fcc_coverage_{isp} = '1' AND fcc_coverage_downspeed_{isp} >= {speed}"

		'''
		sql_statement += "OR "
		if isp == 'verizon' or (isp == 'centurylink' and state in ['AR','NC']):
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_50 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed})) "
		elif isp == 'att':
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_50 = '1' OR fcc_coverage_{isp}_70 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed} OR fcc_coverage_downspeed_{isp}_70 >= {speed} )) "
		elif isp == 'windstream' and state == 'NC':
			sql_statement += f"((fcc_coverage_{isp}_10 = '1' OR fcc_coverage_{isp}_41 = '1' OR fcc_coverage_{isp}_50 = '1') AND (fcc_coverage_downspeed_{isp}_10 >= {speed} OR fcc_coverage_downspeed_{isp}_41 >= {speed} OR fcc_coverage_downspeed_{isp}_50 >= {speed} )) "
		else:
			sql_statement += f"(fcc_coverage_{isp} = '1' AND fcc_coverage_downspeed_{isp} >= {speed}) "'''
		mycursor.execute(sql_statement)

		for row in mycursor.fetchall():
			block = row[0]
			isps_per_block[block].add(isp)
	#pp.pprint(isps_per_block)
	return isps_per_block


# --------------------------------------------------------------------------------------------------
def get_excluded_blocks():
	total_block_count = 0
	excluded_block_count = 0

	total_block_pop = 0
	excluded_block_pop = 0

	for state in STATES:
		print('-------------------------STATE: {}-------------------------'.format(state))
		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		blocks_pop = get_census_block_population_counts(state, mycursor)

		speed = '0'
		# Get all blocks
		sql_statement=f"SELECT addr_census_block, count(*) \
						FROM addresses_{state} \
						WHERE {fcc_covered_sql(state=state,limit_to_tool_blocks=False,speed=speed)} \
						GROUP BY addr_census_block \
						"
		mycursor.execute(sql_statement)
		all_blocks = dict()
		for block_count in mycursor.fetchall():
			all_blocks[block_count[0]] = block_count[1]

		# Get not excluded blocks
		# Get all blocks
		sql_statement=f"SELECT addr_census_block, count(*) \
						FROM addresses_{state} \
						WHERE {fcc_covered_sql(state=state,limit_to_tool_blocks=True,speed=speed,method=2)} \
						GROUP BY addr_census_block \
						"
		#sql_print(sql_statement)
		mycursor.execute(sql_statement)
		not_excluded_blocks = dict()
		for block_count in mycursor.fetchall():
			not_excluded_blocks[block_count[0]] = block_count[1]

		total_block_count += len(all_blocks)
		excluded_block_count += len(all_blocks)-len(not_excluded_blocks)

		# Get excluded blocks
		excluded_blocks = set()
		for block in all_blocks:
			if block not in not_excluded_blocks:
				excluded_blocks.add(block)


		# Get pops
		total_pop = 0
		excluded_pop = 0
		for block in all_blocks:
			total_pop += blocks_pop[block]
		for block in excluded_blocks:
			excluded_pop += blocks_pop[block]

		# Add to summary
		total_block_pop += total_pop
		excluded_block_pop += excluded_pop

		print('-Block-')
		print('All blocks: {}'.format(len(all_blocks)))
		print('Non-excluded blocks: {}'.format(len(not_excluded_blocks)))
		print('Difference: {}'.format(len(all_blocks)-len(not_excluded_blocks)))

		print('-Pop-')
		print('All blocks pop: {}'.format(total_pop))
		print('Excluded pop: {}'.format(excluded_pop))

	print('SUMMARY:')
	print('All blocks: {}'.format(total_block_count))
	print('Difference: {}'.format(excluded_block_count))

	print('All blocks pop: {}'.format(total_block_pop))
	print('Excluded pop: {}'.format(excluded_block_pop))

def a():
	SATELLITE_ISPS = ('ViaSat, Inc.', 'GCI Holdings LLC', 'Hughes Network Systems, LLC', 'VSAT Systems, LLC')
	ALL_ISP_FULL_NAMES = {'Windstream Holdings, Inc.',
		'Charter Communications',
		'Comcast Corporation',
		'CenturyLink, Inc.',
		'AT&T Inc.',
		'Cox Communications, Inc.',
		'Verizon Communications Inc.',
		'Frontier Communications Corporation',
		'Consolidated Communications, Inc.'}


	for state in ['OH']:
		print(state)
		# Connect to mysql database
		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		 database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		STATE_ISP_FULL_NAMES = set()
		for isp in ISPS_PER_STATE[state]:
			STATE_ISP_FULL_NAMES.add(ISP_FULL_NAMES[isp])

		# Get all ISPs in state
		EXCLUDED_ISPS = set()
		mycursor.execute(f"SELECT distinct holding_company_final FROM fcc_coverage_blocks_{state} WHERE holding_company_final not in {SATELLITE_ISPS} and fcc_coverage = '1'")
		for i, row in enumerate(mycursor.fetchall()):
			isp_full_name = row[0]
			if isp_full_name in ALL_ISP_FULL_NAMES and isp_full_name not in STATE_ISP_FULL_NAMES:
				print(isp_full_name)
				EXCLUDED_ISPS.add(isp_full_name)

		# Get all blocks for state in NAD
		BLOCKS_IN_NAD = set()
		mycursor.execute(f"SELECT distinct addr_census_block FROM  addresses_{state} where {is_known_res()}")
		for i, row in enumerate(mycursor.fetchall()):
			BLOCKS_IN_NAD.add(row[0])

		# Get pop per excluded ISP
		blocks_pop = get_census_block_population_counts(state, mycursor)
		excluded_pop_per_isp = defaultdict(lambda:0)
		for excluded_isp in EXCLUDED_ISPS:
			mycursor.execute(f"SELECT distinct census_block FROM fcc_coverage_blocks_{state} WHERE holding_company_final = '{excluded_isp}' and fcc_coverage = '1'")
			for row in mycursor.fetchall():
				block = row[0]

				if block in BLOCKS_IN_NAD:
					excluded_pop_per_isp[excluded_isp] += blocks_pop[block]
					if excluded_isp == 'CenturyLink, Inc.':
						print('HERE')
						print(block)
						print(blocks_pop[block])
		pp.pprint(excluded_pop_per_isp)


main()