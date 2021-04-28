# Broadband Mapping Analysis

This repo contains the code for No WAN's Land, at IMC '20.

You can access the full dataset on [Google Drive](https://drive.google.com/drive/u/3/folders/12mTemnw0QdEr4EGQpImCkmTHVb36IqSL)

## [Paper](https://dl.acm.org/doi/abs/10.1145/3419394.3423652)

## Main Files
- **Dataset** - data/data_{**STATE_ABBR**}.csv - Contains all residential addresses from the [National Address Database](https://www.transportation.gov/gis/national-address-database/national-address-database-0) with their FCC Form 477 coverage and BAT responses from each ISP.
- **Analysis Code** - analysis.ipynb - Generates all tables and figures in the paper.
- **Columns** - columns.csv - Column names for each raw SQL column by state.

## Dataset Columns
| Name | Description | Notes |
|-|-|-|
| addr\_id | Unique ID for each address. |  |
| addr\_line1 | Address number + street name. |  |
| addr\_city | Address city. |  |
| addr\_state | Address state. |  |
| addr\_zip | Address ZIP code. |  |
| addr\_lat | Address latitude. |  |
| addr\_lon | Address longitude. |  |
| addr\_census_block | Address census block. |  |
| addr\_unit_type | Address type (filtered to residential only). |  |
| addr\_unit\_id | Address type ID. |  |
| addr\_full | Concatenated address: "line1 + city + state + zip". |  |
| fcc\_coverage\_{**ISP**}(\_{**TECH CODE**}) | FCC Form 477 coverage of the address by {**ISP**} with technology {**TECH CODE**} (if exists). | 0 = Covered, 1 = Not Covered.  Also, see [FCC tech codes](https://www.fcc.gov/general/technology-codes-used-fixed-broadband-deployment-data). |
| fcc\_coverage\_downspeed\_{**ISP**}(\_{**TECH CODE**}) |  Minimum download speed of the address' census block according to Form 477 by {**ISP**} with technology {**TECH CODE**} (if exists). |  |
| fcc\_coverage\_upspeed\_{**ISP**}(\_{**TECH CODE**}) | Minimum upload speed of the address' census block according to Form 477 by {**ISP**} with technology {**TECH CODE**} (if exists). |  |
| tool\_coverage\_{**ISP**}(\_{**TECH CODE**}) | BAT coverage of the address by {**ISP**} with technology {**TECH CODE**} (if exists). | See analysis.ipynb for the mapping from values to coverage outcomes. |
| tool\_coverage\_downspeed\_{**ISP**}(\_{**TECH CODE**}) | Minimum download speed of the address according to {**ISP**}'s BAT with technology {**TECH CODE**} (if exists). |  |
| tool\_coverage\_upspeed\_{**ISP**}(\_{**TECH CODE**}) | Minimum upload speed of the address according to {**ISP**}'s BAT with technology {**TECH CODE**} (if exists). |  |
| fcc\_coverage\_LOCAL | FCC Form 477 coverage of the address by ANY local **ISP** (as defined in paper). |  |
| addr_dpv | [Delivery Point Validation](https://postalpro.usps.com/address-quality/dpv). Whether the USPS recognizes an address as a valid delivery point. | Queried using [SmartyStreets](https://smartystreets.com/). | |
| addr_rdi | [Residential Delivery Indicator](https://qusps.usps.com/nationalpremieraccounts/rdi.htm). Whether the USPS classifies an address as residential for billing purposes. | Queried using [SmartyStreets](https://smartystreets.com/). |

## Required Files
- **FCC Stack Block Population Estimates** - us2019.csv - [Data](https://www.fcc.gov/file/19314/download), [Info](https://www.fcc.gov/staff-block-estimates)
- **Census Block Urban/Rural Data (Shapefiles)** - block_class/{**STATE**}/tl\_2019\_{**FIPS_CODE**}\_tabblock10.shp - [Data/Info](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)
    - See: [state FIPS codes](https://www.nrcs.usda.gov/wps/portal/nrcs/detail/?cid=nrcs143_013696)
- **ACS Demographic Data** - _NOTE: Use transposed, 5-year estimates._
    - **Race** - ACS/ACSDT5Y2018.B03002_data_with_overlays_2020-12-21T003055.csv - [Data](https://data.census.gov/cedsci/table?q=ACSDT1Y2019.B03002&tid=ACSDT1Y2019.B03002&hidePreview=true), [Info](https://api.census.gov/data/2017/acs/acs1/groups/B03002.html)
    - **Poverty** - ACS/ACSST5Y2018.S1701_data_with_overlays_2020-12-21T002937.csv - [Data](https://data.census.gov/cedsci/table?q=ACSST1Y2019.S1701&tid=ACSST1Y2019.S1701&hidePreview=true), [Info](https://api.census.gov/data/2019/acs/acs1/subject/groups/S1701.html)

## Optional Files
- **FCC Form 477 Data** - fbd_us_without_satellite_jun2018_v1.csv - [Data](http://transition.fcc.gov/form477/BroadbandData/Fixed/Jun18/Version%201/US-Fixed-without-Satellite-Jun2018.zip), [Info](https://www.fcc.gov/general/broadband-deployment-data-fcc-form-477)
    - This was the latest data available at the time of the paper.

- **Border addresses** - Some addresses on the border between two states are included even if the state is not in our dataset. (For example, there are 5 addresses from WV included in our VA dataset.) Since none of the addresses have Form 477 coverage in our dataset, they are effectively excluded from the analysis.
## Known Issues
- **Duplicate addresses** - The National Address Database contains duplicates of street names. For example, analysis.ipynb contains an example of an address that appears a whopping 62 times in our dataset! We did not filter out these cases from our dataset.
