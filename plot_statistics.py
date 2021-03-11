import scipy.stats
import math
import shapefile as shp
from random import random
from collections import defaultdict
from scipy.optimize import curve_fit
import pylab
import numpy as np
import pandas as pd
from mpl_toolkits.axes_grid1 import make_axes_locatable
import pprint
import mysql.connector
import matplotlib.pyplot as plt
import seaborn as sns
import sys
from calculate_statistics import (is_known_res ,get_census_block_population_counts, get_isps_per_block, get_census_block_rural_classification, competition, competition_rural,total_coverage_pop_tool)
from response_breakdowns import ALL_RESPONSES, POS_RESPONSES, NEG_RESPONSES, UNRECOGNIZED_RESPONSES, BUSINESS_RESPONSES, EXCLUDED_RESPONSES, ISPS_PER_STATE, STATES, LABELS, ALL_ISPS

pp = pprint.PrettyPrinter(indent=4)


NULL = '-123'
action = sys.argv[1]


def main():
	if action == 'isp_coverage_zip':
		for state in ['VA','VT','AR']:
			isp_coverage_zip(state)
	elif action == 'total_coverage_zip':
		total_coverage_zip()
	# IN PAPER (?): DISTRIBUTION
	elif action == 'isp_coverage_stats_total':
		isp_coverage_stats_total()
	elif action == 'isp_coverage_block':
		for state in ['VT','AR','VA']:
			isp_coverage_block(state)
	# IN PAPER: competition speed
	elif action == 'competition_block_speed':
		competition_block_speed()
	# IN PAPER: competition urban/rural
	elif action == 'competition_block_rural':
		competition_block_rural()
	# IN PAPER: example bad blocks for visualizations
	elif action == 'get_bad_blocks':
		get_bad_blocks('VA','centurylink')
	# IN PAPER: linear model
	elif action == 'linear_model':
		linear_model()
	elif action == 'linear_model_block_group':
		linear_model_block_group()
	# IN PAPER: speed overstatements
	elif action == 'speed_overstatements':
		speed_overstatements()



		
# --------------------------------------------------------------------------------

def isp_coverage_zip(state):
	# Connect to mysql database
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	if state == 'VA':
		fig, axs = plt.subplots(2, 2,figsize=(10, 10))
	elif state == 'VT':
		fig, axs = plt.subplots(2, 2,figsize=(10, 10))
	elif state == 'AR':
		fig, axs = plt.subplots(3, 2,figsize=(8, 16))
	fig.suptitle('ISPs in {}'.format(LABELS[state]))

	for i_isp, isp in enumerate(ISPS_PER_STATE[state]):
		if isp == 'verizon':
			sql_command = "SELECT a.addr_zip, b.cnt, c.cnt \
				/* Total count */ \
				FROM ( \
					SELECT addr_zip \
					FROM addresses_{} \
					WHERE (fcc_coverage_verizon_10 = '1' or fcc_coverage_verizon_50 = '1') and (tool_coverage_verizon_10 in {} and tool_coverage_verizon_50 in {}) \
					GROUP BY addr_zip \
				) a \
				/* Negative count */ \
				LEFT JOIN ( \
					SELECT addr_zip, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_verizon_10 = '1' or fcc_coverage_verizon_50 = '1') and (tool_coverage_verizon_10 in {} and tool_coverage_verizon_50 in {}) \
					GROUP BY addr_zip \
				) b \
				/* Positive count */ \
				ON a.addr_zip = b.addr_zip \
				LEFT JOIN (\
					SELECT addr_zip, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_verizon_10 = '1' or fcc_coverage_verizon_50 = '1') and (tool_coverage_verizon_10 in {} or tool_coverage_verizon_50 in {}) \
					GROUP BY addr_zip \
				) c \
				ON a.addr_zip = c.addr_zip".format(
					state,
					ALL_RESPONSES[isp], ALL_RESPONSES[isp],
					state,
					NEG_RESPONSES[isp], NEG_RESPONSES[isp],
					state,
					POS_RESPONSES[isp],	POS_RESPONSES[isp],
				)
		elif isp == 'att':
			sql_command = "SELECT a.addr_zip, b.cnt, c.cnt \
				/* Total count */ \
				FROM ( \
					SELECT addr_zip \
					FROM addresses_{} \
					WHERE (fcc_coverage_att_10 = '1' or fcc_coverage_att_50 = '1' or fcc_coverage_att_70 = '1') \
						and (tool_coverage_att_10 in {} and tool_coverage_att_50 in {} and tool_coverage_att_70 in {}) \
					GROUP BY addr_zip \
				) a \
				/* Negative count */ \
				LEFT JOIN ( \
					SELECT addr_zip, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_att_10 = '1' or fcc_coverage_att_50 = '1' or fcc_coverage_att_70 = '1') \
						and (tool_coverage_att_10 in {} and tool_coverage_att_50 in {} and tool_coverage_att_70 in {}) \
					GROUP BY addr_zip \
				) b \
				/* Postivie count */ \
				ON a.addr_zip = b.addr_zip \
				LEFT JOIN (\
					SELECT addr_zip, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_att_10 = '1' or fcc_coverage_att_50 = '1' or fcc_coverage_att_70 = '1') \
						and (tool_coverage_att_10 in {} or tool_coverage_att_50 in {} or tool_coverage_att_70 in {}) \
					GROUP BY addr_zip \
				) c \
				ON a.addr_zip = c.addr_zip".format(
					state,
					ALL_RESPONSES[isp], ALL_RESPONSES[isp], ALL_RESPONSES[isp],
					state,
					NEG_RESPONSES[isp], NEG_RESPONSES[isp], NEG_RESPONSES[isp],
					state,
					POS_RESPONSES[isp],	POS_RESPONSES[isp], POS_RESPONSES[isp],
				)
		elif isp == 'centurylink' and state == 'AR':
			sql_command = "SELECT a.addr_zip, b.cnt, c.cnt \
				FROM ( \
					SELECT addr_zip \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} \
					GROUP BY addr_zip \
				) a \
				LEFT JOIN ( \
					SELECT addr_zip, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} \
					GROUP BY addr_zip \
				) b \
				ON a.addr_zip = b.addr_zip \
				LEFT JOIN (\
					SELECT addr_zip, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} \
					GROUP BY addr_zip \
				) c \
				ON a.addr_zip = c.addr_zip".format(
					state,
					isp, isp, isp, ALL_RESPONSES[isp],
					state,
					isp, isp, isp, NEG_RESPONSES[isp],
					state,
					isp, isp, isp, POS_RESPONSES[isp]
				)
		else:
			sql_command = "SELECT a.addr_zip, b.cnt, c.cnt \
				FROM ( \
					SELECT addr_zip \
					FROM addresses_{} \
					WHERE fcc_coverage_{} = '1' and tool_coverage_{} in {} \
					GROUP BY addr_zip \
				) a \
				LEFT JOIN ( \
					SELECT addr_zip, count(*) as cnt \
					FROM addresses_{} \
					WHERE fcc_coverage_{} = '1' and tool_coverage_{} in {} \
					GROUP BY addr_zip \
				) b \
				ON a.addr_zip = b.addr_zip \
				LEFT JOIN (\
					SELECT addr_zip, count(*) as cnt \
					FROM addresses_{} \
					WHERE fcc_coverage_{} = '1' and tool_coverage_{} in {} \
					GROUP BY addr_zip \
				) c \
				ON a.addr_zip = c.addr_zip".format(
					state,
					isp, isp, ALL_RESPONSES[isp],
					state,
					isp, isp, NEG_RESPONSES[isp],
					state,
					isp, isp, POS_RESPONSES[isp]
				)

		mycursor.execute(sql_command)
		myresult = mycursor.fetchall()

		zip_coverage_ratios = dict()
		zip_coverage_counts = dict()

		print('Total zipcodes: {}'.format(len(myresult)))

		for i, row in enumerate(myresult):

			zipcode = row[0]
			positive_count = row[2]
			if positive_count == None:
				positive_count = 0
			negative_count = row[1]
			if negative_count == None:
				negative_count = 0

			zip_coverage_ratios[zipcode] = positive_count/(positive_count+negative_count)
			zip_coverage_counts[zipcode] = (positive_count+negative_count)

		# ---- Get rurality details:

		data = pd.read_csv('UrbanRural_Zip_{}.csv'.format(state), header=0, sep=',', lineterminator='\n')

		zips_urban = dict()
		zips_rural = dict()
		ratio_zips_urban = dict()
		ratio_zips_rural = dict()

		for i, row in data.iterrows():
			if i == 0:
				continue

			if float(row['D002']) == 0 and float(row['D005']) == 0:
				zips_urban[row['GEO.id2']] = 'N'
				zips_rural[row['GEO.id2']] = 'N'
				ratio_zips_urban[row['GEO.id2']] = 'NA'
				ratio_zips_rural[row['GEO.id2']] = 'NA'
			else:
				zips_urban[row['GEO.id2']] = int(row['D002'])
				zips_rural[row['GEO.id2']] = int(row['D005'])
				ratio_zips_urban[row['GEO.id2']] = float(row['D002']) / (int(row['D002']) + int(row['D005']))
				ratio_zips_rural[row['GEO.id2']] = float(row['D005']) / (int(row['D002']) + int(row['D005']))

		x_values = list()
		y_values = list()
		for zipcode in zip_coverage_ratios.keys():
			if zipcode not in ratio_zips_urban:
				continue
			if ratio_zips_urban[zipcode] != 'NA' and zip_coverage_counts[zipcode] > 50:
				if float(zip_coverage_ratios[zipcode]) > .6:
					x_values.append(float(ratio_zips_urban[zipcode]))
					y_values.append(float(zip_coverage_ratios[zipcode]))

		# Plot Data:

		axs[page_orientations[state][i_isp][0], page_orientations[state][i_isp][1]].axhline(y=1, color='r', linestyle='-')

		x = np.asarray(x_values)
		y = np.asarray(y_values)

		print('ISP: ' + str(isp))
		print('Count: ' + str(len(x_values)))

		axs[page_orientations[state][i_isp][0], page_orientations[state][i_isp][1]].scatter(x, y,s=4)
		axs[page_orientations[state][i_isp][0], page_orientations[state][i_isp][1]].set_title(LABELS[isp])

		z = np.polyfit(x, y, 1)
		p = np.poly1d(z)
		axs[page_orientations[state][i_isp][0], page_orientations[state][i_isp][1]].plot(x,p(x), linewidth=1, alpha=.4)

	if state in ['VA','VT']:
		for i, ax in enumerate(axs.flat):
			# If top row
			if i == 0:
				ax.set(ylabel='% with Broadband Coverage')
			elif i == 2:
				ax.set(xlabel='% Population in Urban Area', ylabel='% with Broadband Coverage')
			elif i == 3:
				ax.set(xlabel='% Population in Urban Area')
	elif state in ['AR']:
		for i, ax in enumerate(axs.flat):
			# If top row
			if i == 0:
				ax.set(ylabel='% with Broadband Coverage')
			if i == 2:
				ax.set(ylabel='% with Broadband Coverage')
			elif i == 4:
				ax.set(xlabel='% Population in Urban Area', ylabel='% with Broadband Coverage')
			elif i == 5:
				ax.set(xlabel='% Population in Urban Area')

	plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=None, hspace=.3)
	plt.show()

# --------------------------------------------------------------------------------

def total_coverage_zip():
	# Must define this
	UNRECOGNIZED_RESPONSES = {
		'att': ('4', NULL),
		'xfinity': ('4',NULL),
		'centurylink': ('0','4'),
		'cox': ('4',NULL),
		'consolidated': ('21',),
		'verizon': ('4',NULL),
		'windstream': ('23',)
	}
	PAGE_ORIENTATIONS = [(0,0),(0,1),(1,0),(1,1)]

	fig, axs = plt.subplots(2, 2,figsize=(10, 10))
	fig.suptitle('Total Coverage Per State')

	for i_state, state in enumerate(['VT', 'VA', 'AR']):
		print('-------------------------STATE: {}-------------------------'.format(state))
		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		### METHOD 1: Get zip codes counts

		# Set up
		sql_statement = "SELECT addr_zip, count(*) FROM addresses_{} ".format(state)
		
		# Set up WHERE
		sql_statement += "WHERE ("

		# FCC coverage is positive for at least one 
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

		# Local coverage must be 0
		sql_statement += "AND (fcc_coverage_LOCAL = '0') "

		# and at least one must be not covered
		sql_statement += "AND ( "
		for i, isp in enumerate(ISPS_PER_STATE[state]):
			if i != 0:
				sql_statement += "OR "
			if isp == 'verizon':
				sql_statement += "(tool_coverage_{}_10 in {} AND tool_coverage_{}_50 in {}) ".format(isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp])
			elif isp == 'att':
				sql_statement += "(tool_coverage_{}_10 in {} AND tool_coverage_{}_50 in {} AND tool_coverage_{}_70 in {}) ".format(isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp])
			else:
				sql_statement += "tool_coverage_{} in {} ".format(isp, NEG_RESPONSES[isp])
		sql_statement += ') '

		# and all others must be not covered, unrecognized, or null
		sql_statement += "AND ( "
		for i, isp in enumerate(ISPS_PER_STATE[state]):
			if i != 0:
				sql_statement += "AND "
			if isp == 'verizon':
				sql_statement += "( (tool_coverage_{}_10 in {} AND tool_coverage_{}_50 in {}) or (tool_coverage_{}_10 is null and tool_coverage_{}_50 is null) ) ".format(isp, NEG_RESPONSES[isp]+UNRECOGNIZED_RESPONSES[isp], isp, NEG_RESPONSES[isp]+UNRECOGNIZED_RESPONSES[isp], isp, isp)
			elif isp == 'att':
				sql_statement += "( (tool_coverage_{}_10 in {} AND tool_coverage_{}_50 in {} AND tool_coverage_{}_70 in {}) or (tool_coverage_{}_10 is null and tool_coverage_{}_50 is null and tool_coverage_{}_70 is null) ) ".format(isp, NEG_RESPONSES[isp]+UNRECOGNIZED_RESPONSES[isp], isp, NEG_RESPONSES[isp]+UNRECOGNIZED_RESPONSES[isp], isp, NEG_RESPONSES[isp]+UNRECOGNIZED_RESPONSES[isp], isp, isp, isp)
			else:
				sql_statement += "(tool_coverage_{} in {} or tool_coverage_{} is null) ".format(isp, NEG_RESPONSES[isp]+UNRECOGNIZED_RESPONSES[isp], isp) 
		sql_statement += ") "

		# Group by zip code
		sql_statement += "GROUP BY addr_zip"

		mycursor.execute(sql_statement)
		zip_counts = mycursor.fetchall()

		print('Total zipcodes: {}'.format(len(zip_counts)))

		total_coverages_per_zip = dict()
		for i, row in enumerate(zip_counts):
			total_coverages_per_zip[row[0]] = row[1]
		method_1_total_coverages_per_zip = total_coverages_per_zip

		count = 0
		for v in total_coverages_per_zip.values():
			count+=v
		print('Total count: {}'.format(count))

		### METHOD 2: Get zip codes counts

		# Set up
		sql_statement = "SELECT addr_zip, count(*) FROM addresses_{} ".format(state)
		
		# Set up WHERE
		sql_statement += "WHERE ("

		# FCC coverage is positive for at least one 
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

		# Local coverage must be 0
		sql_statement += "AND (fcc_coverage_LOCAL = '0') "

		# and at least one must be not covered
		sql_statement += "AND ( "
		for i, isp in enumerate(ISPS_PER_STATE[state]):
			if i != 0:
				sql_statement += "OR "
			if isp == 'verizon':
				sql_statement += "(tool_coverage_{}_10 in {} AND tool_coverage_{}_50 in {}) ".format(isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp])
			elif isp == 'att':
				sql_statement += "(tool_coverage_{}_10 in {} AND tool_coverage_{}_50 in {} AND tool_coverage_{}_70 in {}) ".format(isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp])
			else:
				sql_statement += "tool_coverage_{} in {} ".format(isp, NEG_RESPONSES[isp])
		sql_statement += ') '

		# and all others must be not covered or null
		sql_statement += "AND ( "
		for i, isp in enumerate(ISPS_PER_STATE[state]):
			if i != 0:
				sql_statement += "AND "
			if isp == 'verizon':
				sql_statement += "( (tool_coverage_{}_10 in {} AND tool_coverage_{}_50 in {}) or (tool_coverage_{}_10 is null and tool_coverage_{}_50 is null) ) ".format(isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp], isp, isp)
			elif isp == 'att':
				sql_statement += "( (tool_coverage_{}_10 in {} AND tool_coverage_{}_50 in {} AND tool_coverage_{}_70 in {}) or (tool_coverage_{}_10 is null and tool_coverage_{}_50 is null and tool_coverage_{}_70 is null) ) ".format(isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp], isp, NEG_RESPONSES[isp], isp, isp, isp)
			else:
				sql_statement += "(tool_coverage_{} in {} or tool_coverage_{} is null) ".format(isp, NEG_RESPONSES[isp], isp) 
		sql_statement += ") "

		# Group by zip code
		sql_statement += "GROUP BY addr_zip"

		mycursor.execute(sql_statement)
		zip_counts = mycursor.fetchall()

		print('Total zipcodes: {}'.format(len(zip_counts)))

		total_coverages_per_zip = dict()
		for i, row in enumerate(zip_counts):
			total_coverages_per_zip[row[0]] = row[1]
		method_2_total_coverages_per_zip = total_coverages_per_zip

		### Turn total_coverages_count into %
		sql_statement = "SELECT addr_zip, count(*) FROM addresses_{} WHERE (".format(state)

		for i, isp in enumerate(ISPS_PER_STATE[state]):
			if i != 0:
				sql_statement += "OR "
			if isp == 'verizon' or (isp == 'centurylink' and state == 'AR'):
				sql_statement += "fcc_coverage_{}_10 = '1' OR fcc_coverage_{}_50 = '1' ".format(isp, isp)
			elif isp == 'att':
				sql_statement += "fcc_coverage_{}_10 = '1' OR fcc_coverage_{}_50 = '1' OR fcc_coverage_{}_70 = '1' ".format(isp, isp, isp)
			else:
				sql_statement += "fcc_coverage_{} = '1' ".format(isp)
		sql_statement += ') GROUP BY addr_zip'
		#print(sql_statement)
		mycursor.execute(sql_statement)

		for row in mycursor.fetchall():
			zip_code = row[0]
			count = row[1]
			for total_coverages_per_zip in [method_1_total_coverages_per_zip, method_2_total_coverages_per_zip]:
				if zip_code not in total_coverages_per_zip:
					total_coverages_per_zip[zip_code] = 0
				else:
					total_coverages_per_zip[zip_code] = total_coverages_per_zip[zip_code] / count

		### Get Rurality per zip code

		data = pd.read_csv('UrbanRural_Zip_{}.csv'.format(state), header=0, sep=',', lineterminator='\n')

		ratio_zips_urban = dict()

		for i, row in data.iterrows():
			if i == 0:
				continue

			if float(row['D002']) == 0 and float(row['D005']) == 0:
				ratio_zips_urban[row['GEO.id2']] = 'NA'
			else:
				ratio_zips_urban[row['GEO.id2']] = float(row['D002']) / (int(row['D002']) + int(row['D005']))


		### Create x/y-values for method 1/2 vs rurality
		method_1_x_values = list()
		method_1_y_values = list()
		for zipcode in method_1_total_coverages_per_zip.keys():
			if zipcode not in ratio_zips_urban:
				continue
			if ratio_zips_urban[zipcode] != 'NA' and method_1_total_coverages_per_zip[zipcode] < .3:
				method_1_x_values.append(float(ratio_zips_urban[zipcode]))
				method_1_y_values.append(float(method_1_total_coverages_per_zip[zipcode]))

		method_2_x_values = list()
		method_2_y_values = list()
		for zipcode in method_2_total_coverages_per_zip.keys():
			if zipcode not in ratio_zips_urban:
				continue
			if ratio_zips_urban[zipcode] != 'NA' and method_1_total_coverages_per_zip[zipcode] < .3:
				method_2_x_values.append(float(ratio_zips_urban[zipcode]))
				method_2_y_values.append(float(method_2_total_coverages_per_zip[zipcode]))

		### Plot all values
		axs[PAGE_ORIENTATIONS[i_state][0], PAGE_ORIENTATIONS[i_state][1]].axhline(y=0, color='k', linestyle='-')
		axs[PAGE_ORIENTATIONS[i_state][0], PAGE_ORIENTATIONS[i_state][1]].set_title(LABELS[state])

		colors = ['b', 'g']
		for i, values in enumerate([(method_1_x_values, method_1_y_values), (method_2_x_values, method_2_y_values)]):
			x = np.asarray(values[0])
			y = np.asarray(values[1])

			axs[PAGE_ORIENTATIONS[i_state][0], PAGE_ORIENTATIONS[i_state][1]].scatter(x, y,s=4, color=colors[i])

			z = np.polyfit(x, y, 1)
			p = np.poly1d(z)
			axs[PAGE_ORIENTATIONS[i_state][0], PAGE_ORIENTATIONS[i_state][1]].plot(x,p(x), linewidth=1, alpha=.4,color=colors[i])

	for i, ax in enumerate(axs.flat):
		# If top row
		if i == 0:
			ax.set(ylabel='# without any coverage')
		elif i == 2:
			ax.set(xlabel='% Population in Urban Area', ylabel='# without any coverage')
		elif i == 3:
			ax.set(xlabel='% Population in Urban Area')
	plt.show()

# --------------------------------------------------------------------------------

def linear_model():
	import statsmodels.api as sm
	import statsmodels.formula.api as smf

	# This df will store all the info
	df_tract_data = pd.DataFrame(columns=['tract', 'coverage_avg','nonwhite_per','poverty_per','rural_per','state'])
	data_for_df = list()

	for state in STATES:
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

		# Get coverage data per census block
		coverage_counts = total_coverage_pop_tool(state=state,methods=[2])
		print('Got coverage data...')

		# 1. Get minority details per census tract (minority = non-white or hispanic)
		variable_data = pd.read_csv(f'NonWhiteDataNew/NonWhiteDataNEW{state}.csv', header=0, sep=',', lineterminator='\n')
		minority_count_per_tract = defaultdict(lambda: {
			'minority':dict(), # non-white or hispanic
			'non_minority':dict() # white non-hispanic
		})
		for i, row in variable_data.iterrows():
			if i == 0:
				continue
			# If values are all 0, there is an issue with the row and we should ignore it
			if int(row['B03002_003E']) + int(row['B03002_004E'])+ int(row['B03002_005E']) + int(row['B03002_006E']) + int(row['B03002_007E']) + int(row['B03002_008E']) + int(row['B03002_012E']) == 0:
				continue
			tract = str(str(row['GEO_ID']).split('US')[1])
			minority_count_per_tract[tract]['non_minority'] = int(row['B03002_003E'])
			minority_count_per_tract[tract]['minority'] = int(row['B03002_004E'])+ int(row['B03002_005E']) + int(row['B03002_006E']) + int(row['B03002_007E']) + int(row['B03002_008E']) + int(row['B03002_012E'])
		print('Got racial data...')
		'''
		# 1. Get racial details per census tract
		data = 'Racial' 
		variable_data = pd.read_csv(f'{data}Data/{data}Data{state}.csv', header=0, sep=',', lineterminator='\n')
		racial_count_per_tract = defaultdict(lambda: {
			'white':dict(),
			'nonwhite':dict()
		})
		for i, row in variable_data.iterrows():
			if i == 0:
				continue
			# If values are all 0, there is an issue with the row and we should ignore it
			if int(row['B02001_002E']) == 0 and (int(row['B02001_003E']) + int(row['B02001_004E']) + int(row['B02001_005E']) + int(row['B02001_006E']) + int(row['B02001_007E'])) == 0:
				continue

			tract = str(str(row['GEO_ID']).split('US')[1])
			racial_count_per_tract[tract]['white'] = int(row['B02001_002E'])
			racial_count_per_tract[tract]['nonwhite'] =  int(row['B02001_003E']) + int(row['B02001_004E']) + int(row['B02001_005E']) + int(row['B02001_006E']) + int(row['B02001_007E'])
		print('Got racial data...')
		'''
		# 2. Get income count per census tract
		data = 'Poverty' 
		variable_data = pd.read_csv(f'{data}Data/{data}Data{state}.csv', header=0, sep=',', lineterminator='\n')
		poverty_percent_per_tract = dict()
		for i, row in variable_data.iterrows():
			if i == 0:
				continue
			# If there is an issue with the row, we should ignore it
			if '-' in row['S1701_C03_001E']:
				continue
			tract = str(str(row['GEO_ID']).split('US')[1])
			poverty_percent_per_tract[tract] = float(row['S1701_C03_001E']) / 100.0 #income_per_tract[tract] = float(row['S1901_C01_012E']) 
			#not_poverty_percent[tract] = 1.0 - (float(row['S1701_C03_001E']) / 100.0)
		print('Got poverty data...')

		# 3. Get coverage and % rural per census tract (from census blocks in the tract)
		covered_counts_per_tract = defaultdict(lambda: 0)
		not_covered_counts_per_tract = defaultdict(lambda: 0)
		rural_urban_total_counts_per_tract = defaultdict(lambda:{
			'U': 0,
			'R': 0,
		})

		SPEED = '0'

		for block in set(list(coverage_counts[SPEED][2]['block_covered_counts'].keys())+list(coverage_counts[SPEED][2]['block_not_covered_counts'].keys())):
			if state == 'AR':
				tract = '0' + block[:10]
			else:
				tract = block[:11]

			if block in coverage_counts[SPEED][2]['block_covered_counts']:
				covered_counts_per_tract[tract] += coverage_counts[SPEED][2]['block_covered_counts'][block]
				rural_urban_total_counts_per_tract[tract][blocks_rural_classification[block]] += coverage_counts[SPEED][2]['block_covered_counts'][block]

			if block in coverage_counts[SPEED][2]['block_not_covered_counts']:
				not_covered_counts_per_tract[tract] += coverage_counts[SPEED][2]['block_not_covered_counts'][block]
				rural_urban_total_counts_per_tract[tract][blocks_rural_classification[block]] += coverage_counts[SPEED][2]['block_not_covered_counts'][block]

		# 4. Get ISP count per tract (the % of blocks in each tract covered by each ISP)
		
		# Inititially are isp counts are 0, we will increment isps in the tract
		isps_dict = dict()
		for isp in ALL_ISPS:
			isps_dict[isp] = 0
		isps_per_tract = defaultdict(lambda: dict(isps_dict))

		isps_per_block = get_isps_per_block(state, int(SPEED))
		'''
		dict: {
			'block1': (isp #1, isp #2,... isp #n)
		}
		'''
		# Number of blocks per tract
		blocks_per_tract = defaultdict(lambda: 0)
		for block, isps in isps_per_block.items():
			if state == 'AR':
				tract = '0' + block[:10]
			else:
				tract = block[:11]
			blocks_per_tract[tract] += 1

			for isp in isps:
				isps_per_tract[tract][isp] = isps_per_tract[tract][isp] + 1

		# Turn each count into a proportion of the blocks per state covered by an ISP
		for tract in isps_per_tract:
			for isp in isps_per_tract[tract]:
				isps_per_tract[tract][isp] = isps_per_tract[tract][isp] / blocks_per_tract[tract]

		# 5. Get population per tract
		pop_per_tract = defaultdict(lambda: 0)
		blocks_pop = get_census_block_population_counts(state, mycursor)

		for block, pop in blocks_pop.items():
			if state == 'AR':
				tract = '0' + block[:10]
			else:
				tract = block[:11]
			pop_per_tract[tract] += pop



		'''
		In summary, we have the below information:
			racial % per tract: racial_count_per_tract
			poverty % per tract: poverty_percent_per_tract
			state per tract: (just the current state)
			rural/urban counts per tract = rural_urban_total_counts_per_tract
			coverage counts per tract: covered_counts_per_tract, not_covered_counts_per_tract
			ISPs per tract: isps_per_tract (dict: {dict[isp]})
		'''

		# Let's add all the data to the df
		excluded_count = 0 
		column_names=['tract', 'coverage_avg','minority_per','poverty_per','rural_per','state', 'pop'] + ALL_ISPS
		# ALL_ISPS = ['att','centurylink','consolidated', 'cox', 'xfinity','verizon','windstream','charter','frontier']

		for tract in rural_urban_total_counts_per_tract:
			# We need to have all the relevant data for the tract
			if tract not in minority_count_per_tract or tract not in poverty_percent_per_tract or (tract not in covered_counts_per_tract and tract not in not_covered_counts_per_tract):
				excluded_count += 1
				continue
			data_for_df.append([
				tract, 
				covered_counts_per_tract[tract]/(covered_counts_per_tract[tract]+not_covered_counts_per_tract[tract]),
				minority_count_per_tract[tract]['minority']/ (minority_count_per_tract[tract]['minority'] + minority_count_per_tract[tract]['non_minority']),
				poverty_percent_per_tract[tract],
				rural_urban_total_counts_per_tract[tract]['R']/(rural_urban_total_counts_per_tract[tract]['R']+rural_urban_total_counts_per_tract[tract]['U']),
				state,
				pop_per_tract[tract],
				isps_per_tract[tract]['att'],
				isps_per_tract[tract]['centurylink'],
				isps_per_tract[tract]['consolidated'],
				isps_per_tract[tract]['cox'],
				isps_per_tract[tract]['xfinity'],
				isps_per_tract[tract]['verizon'],
				isps_per_tract[tract]['windstream'],
				isps_per_tract[tract]['charter'],
				isps_per_tract[tract]['frontier'],
			])
			
			'''
			df_row = pd.DataFrame(
					columns=['tract', 'coverage_avg','nonwhite_per','poverty_per','rural_per','state'],
					data=[[
						tract, 
						covered_counts_per_tract[tract]/(covered_counts_per_tract[tract]+not_covered_counts_per_tract[tract]),
						racial_count_per_tract[tract]['nonwhite']/(racial_count_per_tract[tract]['nonwhite']+racial_count_per_tract[tract]['white']),
						poverty_percent_per_tract[tract],
						rural_urban_total_counts_per_tract[tract]['R']/(rural_urban_total_counts_per_tract[tract]['R']+rural_urban_total_counts_per_tract[tract]['U']),
						state
					]])
			df_tract_data = df_tract_data.append(df_row)
			'''

	df_tract_data = pd.DataFrame(data_for_df, columns = column_names)

	print(df_tract_data.head())

	# Print scatter plot
	if True:
		#fig  plt.plot()
		sns.set_style("whitegrid") 

		# Rural
		axs = sns.regplot(x = 'rural_per', y = 'coverage_avg', data = df_tract_data,scatter=True, line_kws={'color': 'red'}, scatter_kws={'s': 1, 'alpha': 0.1}) 
		plt.ylabel("Population Covered (BATs) / Population Covered (FCC)")
		plt.xlabel("Proportion of Population Living In A Rural Area")
		plt.ylim((.83, 1.04)) 
		plt.show()

		axess = sns.regplot(x = 'poverty_per', y = 'coverage_avg', data = df_tract_data, scatter=True, line_kws={'color': 'red'}, scatter_kws={'s': 1, 'alpha': 0.1}) 
		plt.ylabel("Population Covered (BATs) / Population Covered (FCC)")
		plt.xlabel("Proportion of Population That Is Minority")
		plt.ylim((.83, 1.04)) 
		plt.show()
		axs = sns.regplot(x = 'minority_per', y = 'coverage_avg', data = df_tract_data,scatter=True, line_kws={'color': 'red'}, scatter_kws={'s': 1, 'alpha': 0.1}) 
		plt.ylabel("Population Covered (BATs) / Population Covered (FCC)")
		plt.xlabel("Proportion of Population That Is Below Poverty Rate")
		plt.ylim((.83, 1.04)) 
		plt.show()
		exit()


	print('------------------------')
	mod = smf.ols(formula='coverage_avg ~ minority_per + poverty_per + rural_per + C(state) + pop + att + centurylink + consolidated + cox + xfinity + verizon + windstream + charter + frontier', data=df_tract_data)
	lm = mod.fit()
	print(lm.summary())
	return
	from statsmodels.stats.api import anova_lm

	interX_lm = smf.ols("coverage_avg ~ nonwhite_per + poverty_per + rural_per + C(state) + \
		(nonwhite_per * rural_per) + \
		(poverty_per * rural_per) + \
		(poverty_per * nonwhite_per) + \
		(poverty_per * nonwhite_per * rural_per)", data=df_tract_data).fit()

	#table = anova_lm(lm, interX_lm)
	print(interX_lm.summary())
	return
	interX_lm = smf.ols("coverage_avg ~ poverty_per * rural_per + nonwhite_per + C(state)", data=df_tract_data).fit()
	#table = anova_lm(lm, interX_lm)
	print(interX_lm.summary())
	interX_lm = smf.ols("coverage_avg ~ poverty_per * nonwhite_per + rural_per + C(state)", data=df_tract_data).fit()
	#table = anova_lm(lm, interX_lm)
	print(interX_lm.summary())


	return
	### Calculate X and Y data

	tract_racial_x = list()
	tract_coverage_y = list()

	for tract, covered_count in tract_covered_counts.items():
		not_covered_count = tract_not_covered_counts[tract]

		#print(f'covered count: {covered_count}')
		#print(f'not covered count: {not_covered_count}')
		if data == 'Racial':
			if white_count_per_tract[tract] != 0 or nonwhite_count_per_tract[tract] != 0:
				tract_racial_x.append( white_count_per_tract[tract]/(white_count_per_tract[tract]+nonwhite_count_per_tract[tract]) )
				tract_coverage_y.append( covered_count/ (covered_count+not_covered_count))
		elif data == 'Poverty':
			if tract in poverty_percent:
				tract_racial_x.append( poverty_percent[tract] )
				tract_coverage_y.append( covered_count/ (covered_count+not_covered_count))


	return
	# ------------- Old:
	for state in ['AR','VT','VA']:

		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		### Get rural/urban classification for each block
		blocks_rural_classification = get_census_block_rural_classification(state,mycursor)
		print('Stored block rural/urban data...')

		### Get coverage data per census block
		coverage_data = total_coverage_pop_tool(state)
		print('Got coverage data...')

		for data in ['Poverty', 'Racial']:
			for urban_or_rural in [None]:
				if urban_or_rural == 'U':
					urban_or_rural_label = 'Urban Areas'
				elif urban_or_rural == 'R':
					urban_or_rural_label = 'Rural Areas'
				elif urban_or_rural == None:
					urban_or_rural_label = ''

				### Get racial details per census tract
				variable_data = pd.read_csv(f'{data}Data/{data}Data{state}.csv', header=0, sep=',', lineterminator='\n')
				if data == 'Racial':	
					white_count_per_tract = defaultdict(lambda: 0)
					nonwhite_count_per_tract = defaultdict(lambda: 0)
				elif data == 'Poverty':
					poverty_percent = dict()
					not_poverty_percent = dict()

				for i, row in variable_data.iterrows():
					if i == 0:
						continue
					tract = str(str(row['GEO_ID']).split('US')[1])
					if data == 'Racial':
						white_count_per_tract[tract] += int(row['B02001_002E'])
						nonwhite_count_per_tract[tract] +=  int(row['B02001_003E']) + int(row['B02001_004E']) + int(row['B02001_005E']) + int(row['B02001_006E']) + int(row['B02001_007E'])
					elif data == 'Poverty':
						if '-' in row['S1701_C03_001E']:
							continue
						poverty_percent[tract] = float(row['S1701_C03_001E']) / 100.0
						not_poverty_percent[tract] = 1.0 - (float(row['S1701_C03_001E']) / 100.0)
					else:
						raise Exception('Wrong data')

				print('Got racial/poverty data...')

				#'block_covered_counts': block_covered_counts,
				#'block_not_covered_counts' : block_not_covered_counts,

				### Get coverage per tract of census blocks
				tract_covered_counts = defaultdict(lambda: 0)
				tract_not_covered_counts = defaultdict(lambda: 0)

				for block in set(list(coverage_data[2]['block_covered_counts'].keys())+list(coverage_data[2]['block_not_covered_counts'].keys())):
					if blocks_rural_classification[block] == urban_or_rural or urban_or_rural == None:
						#print(block)
						#print(tract)
						if state == 'AR':
							tract = '0' + block[:10]
						else:
							tract = block[:11]

						if block in coverage_data[2]['block_covered_counts']:
							tract_covered_counts[tract] += coverage_data[2]['block_covered_counts'][block]
						else: 
							tract_covered_counts[tract] += 0
						if block in coverage_data[2]['block_not_covered_counts']:
							tract_not_covered_counts[tract] += coverage_data[2]['block_not_covered_counts'][block]
						else:
							tract_not_covered_counts[tract] += 0

				### Calculate X and Y data

				tract_racial_x = list()
				tract_coverage_y = list()

				for tract, covered_count in tract_covered_counts.items():
					not_covered_count = tract_not_covered_counts[tract]

					#print(f'covered count: {covered_count}')
					#print(f'not covered count: {not_covered_count}')
					if data == 'Racial':
						if white_count_per_tract[tract] != 0 or nonwhite_count_per_tract[tract] != 0:
							tract_racial_x.append( white_count_per_tract[tract]/(white_count_per_tract[tract]+nonwhite_count_per_tract[tract]) )
							tract_coverage_y.append( covered_count/ (covered_count+not_covered_count))
					elif data == 'Poverty':
						if tract in poverty_percent:
							tract_racial_x.append( poverty_percent[tract] )
							tract_coverage_y.append( covered_count/ (covered_count+not_covered_count))

				### Plot data

				fig, ax = plt.subplots(figsize=(10, 10))
				ax.axhline(y=1, color='r', linestyle='-')
				x = np.asarray(tract_racial_x)
				y = np.asarray(tract_coverage_y)
				if data == 'Racial':
					ax.xaxis.set_label_text("Proportion of Population that is White")
				elif data == 'Poverty':
					ax.xaxis.set_label_text("Proportion of Population Below Poverty Line")
				ax.yaxis.set_label_text("Average Broadband Coverage")

				ax.scatter(x, y,s=4)
				plt.title(urban_or_rural_label)

				#z = np.polyfit(x, y, 1)
				#p = np.poly1d(z)

				slope, intercept, r, p, stderr = scipy.stats.linregress(x, y)
				line = f'Regression line: y={intercept:.2f}+{slope:.2f}x, r={r:.2f}'
				print(state)
				print(data)
				print(urban_or_rural)
				print(line)
				print(f"P-value: {p}")
				print(f'Std error: {stderr}')

				#ax.plot(x, y, linewidth=0, marker='s', label='Data points')
				ax.plot(x, intercept + slope * x, label=line)
				#ax.plot(x,p(x), linewidth=1, alpha=.4)
				plt.ylim((.78, 1.04)) 
				#plt.show()

# --------------------------------------------------------------------------------

def linear_model_block_group():
	import statsmodels.api as sm
	import statsmodels.formula.api as smf

	# This df will store all the info
	df_tract_data = pd.DataFrame(columns=['block_group', 'coverage_avg','nonwhite_per','poverty_per','rural_per','state'])
	data_for_df = list()

	for state in ['VT']:
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

		pp.pprint(blocks_rural_classification)
		return

		# Get coverage data per census block
		coverage_counts = total_coverage_pop_tool(state)
		print('Got coverage data...')

		# 1. Get racial details per census tract
		variable_data = pd.read_csv(f'RacialData{state}BlockGroup2010.csv', header=0, sep=',', lineterminator='\n')
		racial_count_per_tract = defaultdict(lambda: {
			'white':dict(),
			'nonwhite':dict()
		})
		for i, row in variable_data.iterrows():
			if i == 0:
				continue
			# If values are all 0, there is an issue with the row and we should ignore it
			if int(row['P001002']) == 0:
				continue
			if int(row['P001002']) != int(row['P001003']) + int(row['P001004']) + int(row['P001005']) + int(row['P001006']) + int(row['P001007']) + int(row['P001008']):
				raise Exception()

			bg = str(str(row['GEO_ID']).split('US')[1])
			racial_count_per_bg[bg]['white'] = int(row['P001003'])
			racial_count_per_bg[bg]['nonwhite'] =  int(row['P001004']) + int(row['P001005']) + int(row['P001006']) + int(row['P001007']) + int(row['P001008'])
		print('Got racial data...')

		# 2. Get income count per census tract
		data = 'Poverty' 
		variable_data = pd.read_csv(f'{data}Data/{data}Data{state}.csv', header=0, sep=',', lineterminator='\n')
		poverty_percent_per_tract = dict()
		for i, row in variable_data.iterrows():
			if i == 0:
				continue
			# If there is an issue with the row, we should ignore it
			if '-' in row['S1701_C03_001E']:
				continue
			tract = str(str(row['GEO_ID']).split('US')[1])
			poverty_percent_per_tract[tract] = float(row['S1701_C03_001E']) / 100.0 #income_per_tract[tract] = float(row['S1901_C01_012E']) 
			#not_poverty_percent[tract] = 1.0 - (float(row['S1701_C03_001E']) / 100.0)
		print('Got poverty data...')

		# 3. Get coverage and % rural per census tract (from census blocks in the tract)
		covered_counts_per_tract = defaultdict(lambda: 0)
		not_covered_counts_per_tract = defaultdict(lambda: 0)
		rural_urban_total_counts_per_tract = defaultdict(lambda:{
			'U': 0,
			'R': 0,
		})

		for block in set(list(coverage_counts['25'][2]['block_covered_counts'].keys())+list(coverage_counts['25'][2]['block_not_covered_counts'].keys())):
			if state == 'AR':
				tract = '0' + block[:10]
			else:
				tract = block[:11]

			if block in coverage_counts['25'][2]['block_covered_counts']:
				covered_counts_per_tract[tract] += coverage_counts['25'][2]['block_covered_counts'][block]
				rural_urban_total_counts_per_tract[tract][blocks_rural_classification[block]] += coverage_counts['25'][2]['block_covered_counts'][block]

			if block in coverage_counts['25'][2]['block_not_covered_counts']:
				not_covered_counts_per_tract[tract] += coverage_counts['25'][2]['block_not_covered_counts'][block]
				rural_urban_total_counts_per_tract[tract][blocks_rural_classification[block]] += coverage_counts['25'][2]['block_not_covered_counts'][block]

		# 4. Get ISPs per tract
		
		# Inititially are isps are False, we will set true for the isps in the tract
		isps_dict = dict()
		for isp in ALL_ISPS:
			isps_dict[isp] = False
		isps_per_tract = defaultdict(lambda: dict(isps_dict))

		isps_per_block = get_isps_per_block(state, 25)
		'''
		dict: {
			'block1': (isp #1, isp #2,... isp #n)
		}
		'''
		for block, isps in isps_per_block.items():
			if state == 'AR':
				tract = '0' + block[:10]
			else:
				tract = block[:11]

			for isp in isps:
				isps_per_tract[tract][isp] = True

		# 5. Get population per tract
		pop_per_tract = defaultdict(lambda: 0)
		blocks_pop = get_census_block_population_counts(state, mycursor)

		for block, pop in blocks_pop.items():
			if state == 'AR':
				tract = '0' + block[:10]
			else:
				tract = block[:11]
			pop_per_tract[tract] += pop



		'''
		In summary, we have the below information:
			racial % per tract: racial_count_per_tract
			poverty % per tract: poverty_percent_per_tract
			state per tract: (just the current state)
			rural/urban counts per tract = rural_urban_total_counts_per_tract
			coverage counts per tract: covered_counts_per_tract, not_covered_counts_per_tract
			ISPs per tract: isps_per_tract (dict: {dict[isp]})
		'''

		# Let's add all the data to the df
		excluded_count = 0 
		column_names=['tract', 'coverage_avg','nonwhite_per','poverty_per','rural_per','state', 'pop'] + ALL_ISPS
		# ALL_ISPS = ['att','centurylink','consolidated', 'cox', 'xfinity','verizon','windstream','charter','frontier']

		for tract in rural_urban_total_counts_per_tract:
			# We need to have all the relevant data for the tract
			if tract not in racial_count_per_tract or tract not in poverty_percent_per_tract or (tract not in covered_counts_per_tract and tract not in not_covered_counts_per_tract):
				excluded_count += 1
				continue
			data_for_df.append([
				tract, 
				covered_counts_per_tract[tract]/(covered_counts_per_tract[tract]+not_covered_counts_per_tract[tract]),
				racial_count_per_tract[tract]['nonwhite']/(racial_count_per_tract[tract]['nonwhite']+racial_count_per_tract[tract]['white']),
				poverty_percent_per_tract[tract],
				rural_urban_total_counts_per_tract[tract]['R']/(rural_urban_total_counts_per_tract[tract]['R']+rural_urban_total_counts_per_tract[tract]['U']),
				state,
				pop_per_tract[tract],
				isps_per_tract[tract]['att'],
				isps_per_tract[tract]['centurylink'],
				isps_per_tract[tract]['consolidated'],
				isps_per_tract[tract]['cox'],
				isps_per_tract[tract]['xfinity'],
				isps_per_tract[tract]['verizon'],
				isps_per_tract[tract]['windstream'],
				isps_per_tract[tract]['charter'],
				isps_per_tract[tract]['frontier'],
			])
			
			'''
			df_row = pd.DataFrame(
					columns=['tract', 'coverage_avg','nonwhite_per','poverty_per','rural_per','state'],
					data=[[
						tract, 
						covered_counts_per_tract[tract]/(covered_counts_per_tract[tract]+not_covered_counts_per_tract[tract]),
						racial_count_per_tract[tract]['nonwhite']/(racial_count_per_tract[tract]['nonwhite']+racial_count_per_tract[tract]['white']),
						poverty_percent_per_tract[tract],
						rural_urban_total_counts_per_tract[tract]['R']/(rural_urban_total_counts_per_tract[tract]['R']+rural_urban_total_counts_per_tract[tract]['U']),
						state
					]])
			df_tract_data = df_tract_data.append(df_row)
			'''

	df_tract_data = pd.DataFrame(data_for_df, columns = column_names)

	print(df_tract_data.head())

	print('------------------------')
	mod = smf.ols(formula='coverage_avg ~ nonwhite_per + poverty_per + rural_per + C(state) + pop + att + centurylink + consolidated + cox + xfinity + verizon + windstream + charter + frontier', data=df_tract_data)
	lm = mod.fit()
	print(lm.summary())
	return

def get_coverage_per_isp(state, mycursor):
	### Get rural/urban data per block:
	census_block_rural_classifications = get_census_block_rural_classification(state, mycursor)
	print('Calculated rural/urban classifications per block...')

	state_coverage_data = dict()
	for i_isp, isp in enumerate(ISPS_PER_STATE[state]):
		if isp == 'verizon':
			sql_command = "SELECT a.addr_census_block, b.cnt, c.cnt \
				/* Total count */ \
				FROM ( \
					SELECT addr_census_block \
					FROM addresses_{} \
					WHERE (fcc_coverage_verizon_10 = '1' or fcc_coverage_verizon_50 = '1') and (tool_coverage_verizon_10 in {} and tool_coverage_verizon_50 in {}) and {} \
					GROUP BY addr_census_block \
				) a \
				/* Negative count */ \
				LEFT JOIN ( \
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_verizon_10 = '1' or fcc_coverage_verizon_50 = '1') and (tool_coverage_verizon_10 in {} and tool_coverage_verizon_50 in {}) and {} \
					GROUP BY addr_census_block \
				) b \
				/* Positive count */ \
				ON a.addr_census_block = b.addr_census_block \
				LEFT JOIN (\
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_verizon_10 = '1' or fcc_coverage_verizon_50 = '1') and (tool_coverage_verizon_10 in {} or tool_coverage_verizon_50 in {}) and {} \
					GROUP BY addr_census_block \
				) c \
				ON a.addr_census_block = c.addr_census_block".format(
					state,
					ALL_RESPONSES[isp], ALL_RESPONSES[isp], is_known_res(),
					state,
					NEG_RESPONSES[isp], NEG_RESPONSES[isp], is_known_res(),
					state,
					POS_RESPONSES[isp],	POS_RESPONSES[isp], is_known_res(),
				)
		elif isp == 'att':
			sql_command = "SELECT a.addr_census_block, b.cnt, c.cnt \
				/* Total count */ \
				FROM ( \
					SELECT addr_census_block \
					FROM addresses_{} \
					WHERE (fcc_coverage_att_10 = '1' or fcc_coverage_att_50 = '1' or fcc_coverage_att_70 = '1') \
						and (tool_coverage_att_10 in {} and tool_coverage_att_50 in {} and tool_coverage_att_70 in {})  and {} \
					GROUP BY addr_census_block \
				) a \
				/* Negative count */ \
				LEFT JOIN ( \
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_att_10 = '1' or fcc_coverage_att_50 = '1' or fcc_coverage_att_70 = '1') \
						and (tool_coverage_att_10 in {} and tool_coverage_att_50 in {} and tool_coverage_att_70 in {}) and {} \
					GROUP BY addr_census_block \
				) b \
				/* Postivie count */ \
				ON a.addr_census_block = b.addr_census_block \
				LEFT JOIN (\
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_att_10 = '1' or fcc_coverage_att_50 = '1' or fcc_coverage_att_70 = '1') \
						and (tool_coverage_att_10 in {} or tool_coverage_att_50 in {} or tool_coverage_att_70 in {}) and {} \
					GROUP BY addr_census_block \
				) c \
				ON a.addr_census_block = c.addr_census_block".format(
					state,
					ALL_RESPONSES[isp], ALL_RESPONSES[isp], ALL_RESPONSES[isp], is_known_res(),
					state,
					NEG_RESPONSES[isp], NEG_RESPONSES[isp], NEG_RESPONSES[isp], is_known_res(),
					state,
					POS_RESPONSES[isp],	POS_RESPONSES[isp], POS_RESPONSES[isp], is_known_res(),
				)
		elif isp == 'centurylink' and state in ['AR','NC']:
			sql_command = "SELECT a.addr_census_block, b.cnt, c.cnt \
				FROM ( \
					SELECT addr_census_block \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) a \
				LEFT JOIN ( \
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) b \
				ON a.addr_census_block = b.addr_census_block \
				LEFT JOIN (\
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) c \
				ON a.addr_census_block = c.addr_census_block".format(
					state,
					isp, isp, isp, ALL_RESPONSES[isp], is_known_res(),
					state,
					isp, isp, isp, NEG_RESPONSES[isp], is_known_res(),
					state,
					isp, isp, isp, POS_RESPONSES[isp], is_known_res(),
				)
		elif isp == 'windstream' and state in ['NC']:
			sql_command = "SELECT a.addr_census_block, b.cnt, c.cnt \
				FROM ( \
					SELECT addr_census_block \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_41 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) a \
				LEFT JOIN ( \
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_41 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) b \
				ON a.addr_census_block = b.addr_census_block \
				LEFT JOIN (\
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE (fcc_coverage_{}_10 = '1' or fcc_coverage_{}_41 = '1' or fcc_coverage_{}_50 = '1') and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) c \
				ON a.addr_census_block = c.addr_census_block".format(
					state,
					isp, isp, isp, isp, ALL_RESPONSES[isp], is_known_res(),
					state,
					isp, isp, isp, isp, NEG_RESPONSES[isp], is_known_res(),
					state,
					isp, isp, isp, isp, POS_RESPONSES[isp], is_known_res()
				)
		else:
			sql_command = "SELECT a.addr_census_block, b.cnt, c.cnt \
				FROM ( \
					SELECT addr_census_block \
					FROM addresses_{} \
					WHERE fcc_coverage_{} = '1' and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) a \
				LEFT JOIN ( \
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE fcc_coverage_{} = '1' and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) b \
				ON a.addr_census_block = b.addr_census_block \
				LEFT JOIN (\
					SELECT addr_census_block, count(*) as cnt \
					FROM addresses_{} \
					WHERE fcc_coverage_{} = '1' and tool_coverage_{} in {} and {} \
					GROUP BY addr_census_block \
				) c \
				ON a.addr_census_block = c.addr_census_block".format(
					state,
					isp, isp, ALL_RESPONSES[isp], is_known_res(),
					state,
					isp, isp, NEG_RESPONSES[isp], is_known_res(),
					state,
					isp, isp, POS_RESPONSES[isp], is_known_res(),
				)

		mycursor.execute(sql_command)
		myresult = mycursor.fetchall()

		# All the coverage values we calculate
		urban_block_coverage_ratios = dict()
		urban_block_coverage_ratios_sum = 0

		rural_block_coverage_ratios = dict()
		rural_block_coverage_ratios_sum = 0

		total_block_coverage_ratios = dict()
		total_block_coverage_ratios_sum = 0

		total_block_coverage_counts = dict()

		for i, row in enumerate(myresult):
			block = row[0]
			if block in total_block_coverage_counts:
				raise Exception()

			positive_count = row[2]
			if positive_count == None:
				positive_count = 0
			negative_count = row[1]
			if negative_count == None:
				negative_count = 0
			if positive_count + negative_count == 0:
				#print('skipped: {}'.format(block))
				continue

			if census_block_rural_classifications[block] == 'U':
				urban_block_coverage_ratios[block] = positive_count/(positive_count+negative_count)
				urban_block_coverage_ratios_sum += positive_count/(positive_count+negative_count)
			elif census_block_rural_classifications[block] == 'R':
				rural_block_coverage_ratios[block] = positive_count/(positive_count+negative_count)
				rural_block_coverage_ratios_sum += positive_count/(positive_count+negative_count)
			else:
				raise Exception()

			total_block_coverage_ratios[block] = positive_count/(positive_count+negative_count)
			total_block_coverage_ratios_sum += positive_count/(positive_count+negative_count)
			total_block_coverage_counts[block] = (positive_count+negative_count)


		# Compute average coverage stats
		urban_coverage_ratio_avg = urban_block_coverage_ratios_sum / len(urban_block_coverage_ratios)
		rural_coverage_ratio_avg = rural_block_coverage_ratios_sum / len(rural_block_coverage_ratios)
		total_coverage_ratio_avg = total_block_coverage_ratios_sum / len(total_block_coverage_ratios)

		# Store coverage data for the isp
		state_coverage_data[isp] = {
			'urban_block_coverage_ratios' : urban_block_coverage_ratios, # dict{block: float}
			'urban_block_coverage_ratios_sum' : urban_block_coverage_ratios_sum, # float 

			'rural_block_coverage_ratios' : rural_block_coverage_ratios, # dict{block: float}
			'rural_block_coverage_ratios_sum' : rural_block_coverage_ratios_sum, # float 

			'all_block_coverage_ratios' : total_block_coverage_ratios, # dict{block: float}
			'all_block_coverage_ratios_sum' : total_block_coverage_ratios_sum, # float 
			'all_block_coverage_counts' : total_block_coverage_counts, # dict{block: int}

			'urban_coverage_ratio_avg' : urban_coverage_ratio_avg, # float
			'rural_coverage_ratio_avg' : rural_coverage_ratio_avg, # float
			'total_coverage_ratio_avg' : total_coverage_ratio_avg, # float
		}
		print('Calculated block coverage data for {}. Total blocks: {}'.format(isp, len(total_block_coverage_counts)))
	return state_coverage_data

# Gets distriubtion of coverage in each state
def isp_coverage_stats_per_state():
	for state in ['AR', 'VT', 'VA', 'MA', 'ME', 'NC']:
		mydb = mysql.connector.connect(
			  host="localhost",
			  user="root",
			  passwd="",
			  database="{}_addresses".format(state)
			)
		mycursor = mydb.cursor(buffered=True)

		fig, axes = plt.subplots()
		handles = list()
		for isp in ISPS_PER_STATE[state]:
			print(isp)

			coverages_per_isp = get_coverage_per_isp(state,mycursor)

			column_names = ['block','avg_fcc_coverage', 'avg_tool_coverage']
			df_coverage_per_block = pd.DataFrame(columns = column_names)

			for block, coverage in coverages_per_isp[isp]['all_block_coverage_ratios'].items():
				df_coverage_per_block = df_coverage_per_block.append({
					'block': block,
					'avg_fcc_coverage': 1,
					'avg_tool_coverage': coverage,
				}, ignore_index=True)
			print('creating hist...')

			X = df_coverage_per_block['avg_tool_coverage']
			n = np.arange(1,len(X)+1) / np.float(len(X))
			Xs = np.sort(X)
			line, = axes.step(n,Xs,label=LABELS[isp]) 
			handles.append(line)

		plt.legend(handles=handles)
		plt.ylabel("Percentage of Block with Coverage")
		plt.xlabel("Proportion of Blocks")
		axes.grid(False)
		vals = axes.get_yticks()
		axes.set_yticklabels(['{:,.0%}'.format(x) for x in vals])

		print('showing...')
		plt.show()

		for percentile in [.75,.5,.25,.1]:
			print(f"{percentile} percentile: {df_coverage_per_block.quantile(percentile)['avg_tool_coverage']}")
	plt.show()


# IN PAPER: Gets distriubtion of coverage in each state
def isp_coverage_stats_total():

	rows_per_isp = defaultdict(lambda: list())
	for state in ['VT']:
		mydb = mysql.connector.connect(
			  host="localhost",
			  user="root",
			  passwd="",
			  database="{}_addresses".format(state)
			)
		mycursor = mydb.cursor(buffered=True)

		fig, axes = plt.subplots()
		handles = list()

		# Get coverage data for each isp in the state
		coverages_per_isp = get_coverage_per_isp(state,mycursor)
		for isp in ISPS_PER_STATE[state]:
			print('Calculating for {} in {}'.format(isp,state))

			for block, coverage in coverages_per_isp[isp]['all_block_coverage_ratios'].items():
				rows_per_isp[isp].append([block, 1, coverage])
				'''
				df_coverages_per_isp[isp] = df_coverages_per_isp[isp].append({
					'block': block,
					'avg_fcc_coverage': 1,
					'avg_tool_coverage': coverage,
				}, ignore_index=True)
				'''

	column_names = ['block','avg_fcc_coverage', 'avg_tool_coverage']

	# Get distribution in each isp
	for isp in sorted(rows_per_isp):

		df_isp = pd.DataFrame(rows_per_isp[isp], columns = column_names)

		print('FINAL INFO: {}'.format(isp))
		X = df_isp['avg_tool_coverage']
		n = np.arange(1,len(X)+1) / np.float(len(X))
		Xs = np.sort(X)
		line, = axes.step(n,Xs,label=LABELS[isp]) 
		handles.append(line)

		for percentile in [.75,.5,.25,.1]:
			print(f"{percentile} percentile: {df_isp.quantile(percentile)['avg_tool_coverage']}")

	print('Creating hist...')
	plt.legend(handles=handles)
	plt.ylabel("Percentage of Block with Coverage")
	plt.xlabel("Proportion of Blocks")
	axes.grid(False)
	vals = axes.get_yticks()
	axes.set_yticklabels(['{:,.0%}'.format(x) for x in vals])

	print('showing...')
	plt.show()



def isp_coverage_block(state):
	print(f'-----------STATE: {state}-------')
	# Connect to mysql database
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	### Get coverage data for each ISP:
	state_coverage_data = get_coverage_per_isp(state, mycursor)

	# data to plot
	n_groups = len(ISPS_PER_STATE[state])
	fcc_coverage = list()
	avg_total_coverage = list()
	avg_urban_coverage = list()
	avg_rural_coverage = list()
	tick_labels = list()

	for isp in ISPS_PER_STATE[state]:
		fcc_coverage.append(1)
		avg_total_coverage.append(state_coverage_data[isp]['total_coverage_ratio_avg'])
		avg_urban_coverage.append(state_coverage_data[isp]['urban_coverage_ratio_avg'])
		avg_rural_coverage.append(state_coverage_data[isp]['rural_coverage_ratio_avg'])
		tick_labels.append(LABELS[isp])

	# create plot
	fig, ax = plt.subplots(figsize=(12,8))
	index = np.arange(n_groups)
	bar_width = 0.15
	opacity = 0.65

	rects1 = plt.bar(index, fcc_coverage, bar_width,
	alpha=opacity,
	color='b',
	label='All Pops (Accord. to FCC)',
	hatch='/')

	rects2 = plt.bar(index + bar_width, avg_total_coverage, bar_width,
	alpha=opacity,
	color='orange',
	label='Urban + Rural Pop (Accord. to Tool)')

	rects3 = plt.bar(index + (bar_width*2), avg_urban_coverage, bar_width,
	alpha=opacity-.2,
	color='b',
	label='Urban Pop (Accord. to Tool)')

	rects4 = plt.bar(index + (bar_width*3), avg_rural_coverage, bar_width,
	alpha=opacity,
	color='c',
	label='Rural Pop (Accord. to Tool)')

	plt.xlabel('ISP')
	plt.ylabel('Proportion of Population Covered by ISP')
	plt.title(f'Broadband Coverage per ISP in {LABELS[state]}')
	plt.xticks(index + bar_width, tick_labels)
	plt.ylim((.2, 1.1)) 
	plt.legend()

	plt.tight_layout()
	plt.show()

# --------------------------------------------------------------------------------

def competition_block_speed():
	states = STATES
	fig, axes = plt.subplots(nrows=3,ncols=3, sharey=True)

	for i, state in enumerate(states):

		ax_row = math.floor(i / (len(states)/3))
		ax_col = int(i % (len(states)/3))

		print(f'Row: {ax_row}')
		print(f'Col: {ax_col}')

		column_names = ['block', 'speed', 'avg_tool_count', 'avg_fcc_count', 'overstatement']
		rows = list()

		# Get competition data broken down by rural/urban
		for speed in ['0','25']:
			state_competition_data = competition_rural(state=state,speed=speed)
			print('Calculated competition data...')

			# Rural blocks
			for block, tool_avg in state_competition_data['tool_rural_isp_avg_per_block'].items():
				avg_fcc_count = state_competition_data['fcc_rural_isp_avg_per_block'][block]
				overstatement = state_competition_data['rural_overstatement_per_block'][block]
				if avg_fcc_count > 1:
					rows.append([block, speed, tool_avg, avg_fcc_count, overstatement])

			# Urban blocks
			for block, tool_avg in state_competition_data['tool_urban_isp_avg_per_block'].items():
				avg_fcc_count = state_competition_data['fcc_urban_isp_avg_per_block'][block]
				overstatement = state_competition_data['urban_overstatement_per_block'][block]
				if avg_fcc_count > 1:
					rows.append([block, speed, tool_avg, avg_fcc_count, overstatement])

		df_counts_per_block = pd.DataFrame(rows, columns = column_names)
		# load the dataset 
		sns.set_style("whitegrid") 

		ax = sns.boxplot(x = 'speed', y = 'overstatement', data = df_counts_per_block,fliersize=0,ax=axes[ax_row][ax_col], order=['0','25']) 
		if ax_col == 0 and ax_row != 1:
			ax.set_ylabel("Proportion of # of Providers Per Block (BATs)")
		else:
			ax.set_ylabel("")
			#ax.get_legend().remove()
		ax.set_xlabel("")
		ax.set_title("{}".format(LABELS[state]))

	plt.show()
	'''
		for FCC_COUNT in PLOTTED_FCC_COUNTS[state]:
			print('FCC COUNT: {}'.format(FCC_COUNT))
			df_at_fcc_count = df_counts_per_block[['avg_fcc_count','avg_tool_count']][df_counts_per_block.avg_fcc_count==FCC_COUNT]

			print('.1')
			print(df_at_fcc_count.quantile(.1))
			print()

			print('.25')
			percen25 = df_at_fcc_count.quantile(.25)['avg_tool_count']
			print(df_at_fcc_count.quantile(.25))
			print('percentile: {}'.format(percen25))
			print()

			print('.5')
			print(df_at_fcc_count.quantile(.5))
			print()

			print('.75')
			percen75 = df_at_fcc_count.quantile(.75)['avg_tool_count']
			print(df_at_fcc_count.quantile(.75))
			print('percentile: {}'.format(percen75))
			print()

			iqr = percen75 - percen25
			print('IQR')
			print(iqr)
			print()

			min_ = percen25 - (1.5 * iqr)
			print('MIN')
			print(min_)

			percen25 = df_at_fcc_count.quantile(.25)['avg_tool_count']
			percen75 = df_at_fcc_count.quantile(.75)['avg_tool_count']
			iqr = percen75 - percen25
			min_ = percen25 - (1.5 * iqr)
			print('MIN: {}'.format(min_))
			y = df_counts_per_block.avg_tool_count[df_counts_per_block.avg_fcc_count==FCC_COUNT]
			#print(y)
			y = y[y<min_-.04]
			#print(y)
			# Add some random "jitter" to the x-axis
			x = np.random.normal(FCC_COUNT-2, 0.04, size=len(y))
			ax.plot(x, y, 'r.', alpha=0.1)
		plt.ylim(-0.2,3.2)
		plt.suptitle("")
	'''

# --------------------------------------------------------------------------------

def competition_block_rural():

	states = STATES
	fig, axes = plt.subplots(nrows=3,ncols=3, sharey=True)

	for i, state in enumerate(states):

		ax_row = math.floor(i / (len(states)/3))
		ax_col = int(i % (len(states)/3))

		print(f'Row: {ax_row}')
		print(f'Col: {ax_col}')

		# Get competition data broken down by rural/urban
		state_competition_data = competition_rural(state=state,speed='25')
		print('Calculated competition data...')

		column_names = ['block', 'Rural/Urban', 'avg_tool_count', 'avg_fcc_count', 'overstatement']
		#df_counts_per_block = pd.DataFrame(columns = column_names)
		rows = list()

		# Rural blocks
		for block, tool_avg in state_competition_data['tool_rural_isp_avg_per_block'].items():
			avg_fcc_count = state_competition_data['fcc_rural_isp_avg_per_block'][block]
			overstatement = state_competition_data['rural_overstatement_per_block'][block]
			if avg_fcc_count > 1:
				rows.append([block, 'Rural', tool_avg, avg_fcc_count, overstatement])

				# Also add across all blocks
				rows.append([block, 'Total', tool_avg, avg_fcc_count, overstatement])
				'''
				df_counts_per_block = df_counts_per_block.append({
						'block': block,
						'Rural/Urban': 'Rural',
						'avg_tool_count': tool_avg,
						'avg_fcc_count': avg_fcc_count,
					}, ignore_index=True)
				'''
		# Urban blocks
		for block, tool_avg in state_competition_data['tool_urban_isp_avg_per_block'].items():
			avg_fcc_count = state_competition_data['fcc_urban_isp_avg_per_block'][block]
			overstatement = state_competition_data['urban_overstatement_per_block'][block]
			if avg_fcc_count > 1:
				rows.append([block, 'Urban', tool_avg, avg_fcc_count, overstatement])

				# Also add across all blocks
				rows.append([block, 'Total', tool_avg, avg_fcc_count, overstatement])
				'''
				df_counts_per_block = df_counts_per_block.append({
						'block': block,
						'Rural/Urban': 'Urban',
						'avg_tool_count': tool_avg,
						'avg_fcc_count': avg_fcc_count,
					}, ignore_index=True)
				'''
		df_counts_per_block = pd.DataFrame(rows, columns = column_names)
		# load the dataset 
		sns.set_style("whitegrid") 

		ax = sns.boxplot(x = 'Rural/Urban', y = 'overstatement', data = df_counts_per_block,fliersize=0,ax=axes[ax_row][ax_col], order=['Total','Urban','Rural']) 
		if ax_col == 0 and ax_row != 1:
			ax.set_ylabel("Proportion of # of Providers Per Block (BATs)")
		else:
			ax.set_ylabel("")
			#ax.get_legend().remove()
		ax.set_xlabel("")
		ax.set_title("{}".format(LABELS[state]))

	plt.show()
	'''
	def autolabel(rects2, bar_percentages):
		for i,rect in enumerate(rects2):
			height = rect.get_height()
			ax.text(rect.get_x() + rect.get_width(), 1.01*height,
				bar_percentages[i],
				ha='center', va='bottom', rotation=0)
	# data to plot
	n_groups = 3
	fcc_competition_avgs = [state_competition_data['fcc_total_isp_avgs_avg'], state_competition_data['fcc_urban_isp_avgs_avg'], state_competition_data['fcc_rural_isp_avgs_avg']]
	tool_competition_avgs = [state_competition_data['tool_total_isp_avgs_avg'], state_competition_data['tool_urban_isp_avgs_avg'], state_competition_data['tool_rural_isp_avgs_avg']]

	tick_labels = ['All Blocks', 'Urban Blocks', 'Rural Blocks']

	# create plot
	fig, ax = plt.subplots()
	index = np.arange(n_groups)
	bar_width = 0.15

	rects1 = plt.bar(index, fcc_competition_avgs, bar_width,
	alpha=.8,
	color='b',
	label='FCC')

	rects2 = plt.bar(index + bar_width, tool_competition_avgs, bar_width,
	alpha=.1,
	color='b',
	label='Tool')
	bar_percentages = list()
	for i in range(len(tool_competition_avgs)):
		percent = (tool_competition_avgs[i]/fcc_competition_avgs[i]) * 100
		bar_percentages.append('{:.1f}%'.format(percent))
	autolabel(rects2,bar_percentages)


	plt.xlabel('Census Block Characteristics')
	plt.ylabel('Avg number of non-local ISPs per block')
	plt.title(f'Broadband Coverage per ISP in {LABELS[state]}')
	plt.xticks(index + bar_width, tick_labels)
	#plt.ylim((.2, 1.1)) 
	plt.legend()

	plt.tight_layout()
	plt.show()
	'''

# --------------------------------------------------------------------------------

def get_bad_blocks(state,isp):

	def read_shapefile(sf):
	    """
	    Read a shapefile into a Pandas dataframe with a 'coords' 
	    column holding the geometry information. This uses the pyshp
	    package
	    """
	    fields = [x[0] for x in sf.fields][1:]
	    print(fields)
	    #records = sf.records()
	    records = [y[:] for y in sf.records()]
	    print(records[0])
	    shps = [s.points for s in sf.shapes()]
	    df = pd.DataFrame(columns=fields, data=records)
	    df = df.assign(coords=shps)
	    return df

	def plot_shape(id, unit_info, ax, s=None):
	    """ PLOTS A SINGLE SHAPE """
	    #plt.figure()
	    #ax = plt.axes()
	    ax.set_aspect('equal')

	    shape_ex = sf.shape(id)
	    x_lon = np.zeros((len(shape_ex.points),1))
	    y_lat = np.zeros((len(shape_ex.points),1))
	    for ip in range(len(shape_ex.points)):
	        x_lon[ip] = shape_ex.points[ip][0]
	        y_lat[ip] = shape_ex.points[ip][1]

	    # Get rid of ticks on axes
	    ax.tick_params(
		    axis='both',          # changes apply to the x-axis
		    which='both',      # both major and minor ticks are affected
		    bottom=False,      # ticks along the bottom edge are off
		    top=False,
		    left=False,
		    right=False,         # ticks along the top edge are off
		    labelbottom=False,
		    labelleft=False) # labels along the bottom edge are off

	    #ax.set_ticks([])
	    #ax.set_tick_labels([])
	    ax.xaxis.set_label_text("")
	    ax.yaxis.set_label_text("")
	    #plt.yticks(y_lat, "")
	    ax.plot(x_lon,y_lat) 
	    ax.set_title('Block: {}'.format(s))

	    # use bbox (bounding box) to set plot limits
	    #plt.xlim(shape_ex.bbox[0],shape_ex.bbox[2])
	    # Plot coverage marker for each households
	    for addr,info in unit_info.items():
	    	if info['marker'] in ['o','x']:
	    		ax.plot(info['lon'], info['lat'], marker=info['marker'], markersize=5, color=info['color'])
	    	elif info['marker'] in ['?', '-']:
	    		ax.text(info['lon'], info['lat'], info['marker'], fontsize=8)
	    	else:
	    		raise Exception()
	    x0 = np.mean(x_lon)
	    y0 = np.mean(y_lat)
	    return x0, y0

	state = 'WI'
	isp = 'att'
	print('-------------------------STATE: {}-------------------------'.format(state))
	# Connect to mysql database
	mydb = mysql.connector.connect(
	  host="localhost",
	  user="root",
	  passwd="",
	  database="{}_addresses".format(state)
	)

	mycursor = mydb.cursor(buffered=True)

	# Read block data
	sf = shp.Reader(f"/Users/DavidM/School/Thesis/Internet-Coverage-Mapping/census_blocks_rural_{state}/census_blocks_{state}.shp")
	df = read_shapefile(sf)

	# Get coverd ratio per block
	coverages_per_isp = get_coverage_per_isp(state,mycursor)
	for v in coverages_per_isp[isp]:
		print(v)

	# Select blocks with bad coverage - or sometimes we do it manually
	if False:
		blocks = list()
		for block, ratio in coverages_per_isp[isp]['all_block_coverage_ratios'].items():
			if ratio < .1 and ratio != 0:
				if len(blocks) < 10:
					blocks.append(block)
					print(block)
					print(ratio)
					print()
		
		print(blocks)
		print(len(blocks))
		if len(blocks) != 10:
			raise Exception()
	else:
		blocks = ['550090205033002','550090002002005','550090001001030', '550090207022016']

	fig, axs = plt.subplots(2,2)
	fig.set_tight_layout(True)
	fig.suptitle('{}'.format(LABELS[isp]),verticalalignment='bottom')
	print(axs)
	i = 0
	
	for ax_row in axs:
		for ax in ax_row:

			# Get all units in first block in the list and parse relevant info 
			unit_info = dict()
			if isp == 'att':
				mycursor.execute(f"SELECT addr_lat, addr_lon, tool_coverage_{isp}_10, tool_coverage_{isp}_50, tool_coverage_{isp}_70, addr_full FROM addresses_{state} WHERE addr_census_block = '{blocks[i]}' and {is_known_res()}")
			else:
				mycursor.execute(f"SELECT addr_lat, addr_lon, tool_coverage_{isp}, addr_full FROM addresses_{state} WHERE addr_census_block = '{blocks[i]}' and {is_known_res()}")

			for row in mycursor.fetchall():
				if isp == 'att':
					lat = float(row[0])
					lon = float(row[1])
					coverage_response10 = row[2]
					coverage_response50 = row[3]
					coverage_response70 = row[4]
					addr = row[5]

					if coverage_response10 in POS_RESPONSES[isp] or coverage_response50 in POS_RESPONSES[isp] or coverage_response70 in POS_RESPONSES[isp]:
						marker = 'o'
						color = 'green'
					elif coverage_response10 in NEG_RESPONSES[isp] and coverage_response50 in NEG_RESPONSES[isp] and coverage_response70 in NEG_RESPONSES[isp]:
						marker = 'x'
						color = 'red'
					elif coverage_response10 in UNRECOGNIZED_RESPONSES[isp] or coverage_response50 in UNRECOGNIZED_RESPONSES[isp] or coverage_response70 in UNRECOGNIZED_RESPONSES[isp]:
						marker = '?'
						color = 'black'
					elif coverage_response10 in EXCLUDED_RESPONSES[isp] or coverage_response50 in EXCLUDED_RESPONSES[isp] or coverage_response70 in EXCLUDED_RESPONSES[isp]:
						marker = '-'
						color = 'black'
					else:
						continue
				else:
					lat = float(row[0])
					lon = float(row[1])
					coverage_response = row[2]
					addr = row[3]

					if coverage_response in POS_RESPONSES[isp]:
						marker = 'o'
						color = 'green'
					elif coverage_response in NEG_RESPONSES[isp]:
						marker = 'x'
						color = 'red'
					elif coverage_response in UNRECOGNIZED_RESPONSES[isp]:
						marker = '?'
						color = 'black'
					elif coverage_response in EXCLUDED_RESPONSES[isp]:
						marker = '-'
						color = 'black'
					else:
						continue

				unit_info[addr] = {'lat':lat,'lon':lon,'marker':marker, 'color':color}

			block = blocks[i]
			print('BLOCK: {}'.format(block))
			print(row)
			pp.pprint(unit_info)


			# Graph the units for the block
			if state == 'AR':
				block = '0'+block
			block_id = df[df.GEOID10==block].index.get_values()[0]
			print('-------')
			plot_shape(block_id, unit_info, ax, block)
			i +=1
	plt.show()

	# --------------------------------------------------------------------------------

def speed_overstatements():
	
	# Specify fields for values we're storing
	column_names = ['Maximum Download Speed (Mbps)', 'ISP', 'Source', 'Urban/Rural']
	values = list()

	# Set up figure across all states
	fig, axes = plt.subplots(ncols=4, sharey=True)

	for state in STATES:
		print(f'State: {state}')
		isps = ['att','centurylink','consolidated','windstream']

		mydb = mysql.connector.connect(
		  host="localhost",
		  user="root",
		  passwd="",
		  database="{}_addresses".format(state)
		)
		mycursor = mydb.cursor(buffered=True)

		# Get urban/rural classifications
		blocks_rural_classification = get_census_block_rural_classification(state,mycursor)

		for isp in isps:
			if isp in ISPS_PER_STATE[state]:
				print(f'--->ISP: {isp}')

				if isp == 'centurylink' and state in ['AR', 'NC']:
					mycursor.execute(f"SELECT fcc_coverage_downspeed_centurylink_10, fcc_coverage_downspeed_centurylink_50, tool_coverage_downspeed_centurylink, addr_census_block FROM addresses_{state} where (fcc_coverage_centurylink_10 = '1' or fcc_coverage_centurylink_50 = '1') and tool_coverage_centurylink = '1' ")
				elif (isp == 'centurylink' and state in ['VA','OH','WI']) or isp == 'consolidated' or (isp == 'windstream' and state in ['AR','OH']):
					mycursor.execute(f"SELECT fcc_coverage_downspeed_{isp}, tool_coverage_downspeed_{isp}, addr_census_block FROM addresses_{state} where (fcc_coverage_{isp} = '1') and tool_coverage_{isp} = '1' ")
				elif isp == 'att':
					mycursor.execute(f"SELECT fcc_coverage_downspeed_att_10, fcc_coverage_downspeed_att_50, tool_coverage_downspeed_att_10, tool_coverage_downspeed_att_50, addr_census_block FROM addresses_{state} where (fcc_coverage_att_10 = '1' or fcc_coverage_att_50 = '1') and (tool_coverage_att_10 in ('2','3') or tool_coverage_att_50 in ('2','3')) ")
				elif isp == 'windstream' and state == 'NC':
					mycursor.execute(f"SELECT fcc_coverage_downspeed_windstream_10, fcc_coverage_downspeed_windstream_41, fcc_coverage_downspeed_windstream_50, tool_coverage_downspeed_windstream, addr_census_block FROM addresses_{state} where (fcc_coverage_windstream_10 = '1' or fcc_coverage_windstream_41 = '1' or fcc_coverage_windstream_50 = '1') and tool_coverage_windstream = '1' ")
				else:
					raise Exception()
				
				for row in mycursor.fetchall():
					if isp == 'centurylink' and state in ['AR','NC']:
						max_downspeed_fcc = max(float(row[0]),float(row[1]))
						max_downspeed_client = float(row[2])
						block = row[3]
					elif (isp == 'centurylink' and state in ['VA','OH','WI']) or isp == 'consolidated' or (isp == 'windstream' and state in ['AR','OH']):
						max_downspeed_fcc = float(row[0])
						max_downspeed_client = float(row[1])
						block = row[2]
					elif isp == 'att':
						max_downspeed_fcc = max(float(row[0]), float(row[1]))
						# The ATT downspeed values can be '', so need to convert it to -1 and then take max
						if row[2] == '':
							max_downspeed_client_10 = -1
						else:
							max_downspeed_client_10 = float(row[2])
						if row[3] == '':
							max_downspeed_client_50 = -1
						else:
							max_downspeed_client_50 = float(row[3])
						max_downspeed_client = max(max_downspeed_client_10, max_downspeed_client_50)
						block = row[4]
					elif isp == 'windstream' and state == 'NC':
						max_downspeed_fcc = max(float(row[0]), float(row[1]),float(row[2]))
						max_downspeed_client = float(row[3])
						block = row[4]
					else:
						raise Exception()

					if max_downspeed_fcc <= 0:
						print(row)
						raise Exception
					if max_downspeed_client <= 0:
						print(row)
						raise Exception

					# Add FCC and BAT data for urban/rural plot
					values.append([max_downspeed_fcc, LABELS[isp], 'FCC', LABELS[blocks_rural_classification[block]]])
					values.append([max_downspeed_client, LABELS[isp], 'BATs', LABELS[blocks_rural_classification[block]]])

					# Add FCC and BAT data for "total" plot
					values.append([max_downspeed_fcc, LABELS[isp], 'FCC', 'Total'])
					values.append([max_downspeed_client, LABELS[isp], 'BATs', 'Total'])



	df_speed_counts = pd.DataFrame(values, columns = column_names)

	# Get quantile info
	print('Urban/rural breakdown:')
	for i, isp in enumerate(['att','centurylink','consolidated','windstream']):
		for urban_or_rural in ['Urban','Rural']:
			df_isp = df_speed_counts.loc[(df_speed_counts['ISP'] == LABELS[isp]) & (df_speed_counts['Urban/Rural'] == urban_or_rural)]
			#df.loc[df['column_name'] == some_value]

			df_isp_fcc = df_isp.loc[df_isp['Source'] == 'FCC']
			df_isp_client = df_isp.loc[df_isp['Source'] == 'Client']

			print(f'FCC Media for {isp} ({urban_or_rural}): {df_isp_fcc.median()}')
			print(f'Client Media for {isp} ({urban_or_rural}): {df_isp_client.median()}')
	df_all_fcc = df_speed_counts.loc[df_speed_counts['Source'] == 'FCC']
	df_all_client = df_speed_counts.loc[df_speed_counts['Source'] == 'Client']

	for i, isp in enumerate(['att','centurylink','consolidated','windstream']):
		df_isp = df_speed_counts.loc[df_speed_counts['ISP'] == LABELS[isp] ]
		#df.loc[df['column_name'] == some_value]

		df_isp_fcc = df_isp.loc[df_isp['Source'] == 'FCC']
		df_isp_client = df_isp.loc[df_isp['Source'] == 'Client']

		print(f'FCC Media for {isp}: {df_isp_fcc.median()}')
		print(f'Client Media for {isp}: {df_isp_client.median()}')
	df_all_fcc = df_speed_counts.loc[df_speed_counts['Source'] == 'FCC']
	df_all_client = df_speed_counts.loc[df_speed_counts['Source'] == 'Client']

	print(f'FCC Media for all: {df_all_fcc.median()}')
	print(f'Client Media for all: {df_all_client.median()}')

	# plot for each state
	print('General breakdown:')
	for i, isp in enumerate(['att','centurylink','consolidated','windstream']):

		sns.set_style("whitegrid") 
		ax = sns.boxplot(x = 'Urban/Rural', y = 'Maximum Download Speed (Mbps)', hue='Source', data = df_speed_counts.loc[df_speed_counts['ISP'] == LABELS[isp]],showfliers=False,ax=axes[i], order=['Total','Urban','Rural'], palette="Blues") 
		handles, labels = ax.get_legend_handles_labels()
		ax.legend(handles=handles, labels=labels)
		ax.set_xlabel('')
		ax.set_yscale("log")
		#ßax.set_ylim(-10,210)

		if i == 0:
			ax.set_ylabel("Maximum Download Speed (Mbps)")
		else:
			ax.set_ylabel("")
			ax.get_legend().remove()
		ax.set_xlabel("")
		ax.set_title("{}".format(LABELS[isp]))

	plt.show()


	exit()


main()