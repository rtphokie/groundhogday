import unittest
from bs4 import BeautifulSoup
import re
import requests, requests_cache
from pprint import pprint
import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
import datetime
requests_cache.install_cache('climate_office_cache') # be kind during testing
key_darksky = '840801c93167d68dbd68611ee068e31b'

whistle_pigs = ['wally', 'phil', 'snerd']

# source: https://www.groundhog.org/Files/Admin/history/UpdatedGroundhog_Day_Predictions.pdf
punxsutawney_phil_saw_his_shadow = {'2019': False,
                                    '2018': True,
                                    '2017': True,
                                    '2016': False,
                                    '2015': True,
                                    '2014': True,
                                    '2013': False,
                                    '2012': True,
                                    '2011': False,
                                    '2010': True,
                                    '2009': True,
                                    '2008': True,
                                    '2007': False,
                                    '2006': True,
                                    '2005': True,
                                    '2004': True,
                                    '2003': True,
                                    '2002': True,
                                    '2001': True,
                                    '2000': True,
                                    }

# source: News and Observer
snerd_shaw_his_shadow = {'2019': True,
                         '2018': True,
                         '2017': True,
                         '2016': False,
                         '2015': False, # snerd first prediction
                         '2014': True,
                         '2013': True,
                         '2012': True,
                         '2011': False,
                         '2010': True,
                         '2009': False,
                         '2008': False,
                         '2007': True, # mortimer first
                         '2006': None,
                         '2005': None,
                         '2004': None,
                         '2003': None,
                         '2002': None,
                         '2001': None,
                         '2000': None,
                         }


def get_nc_climate_office_page(year):
    url = f"https://climate.ncsu.edu/climate/groundhog/record?year={year}"
    page = requests.get(url)
    pattern = re.compile("Sir Walter Wally's Prediction for [0-9]+ was (.*)\.")
    soup = BeautifulSoup(page.content, 'html.parser')

    # init from hard coded histories
    shadows = { 'phil': punxsutawney_phil_saw_his_shadow[str(year)],
                'snerd': snerd_shaw_his_shadow[str(year)]}

    # wally's prediction
    for p in soup.find_all('p'):
        m = pattern.match(p.text)
        if m:
            prediction = m.group(1)
            if "spring" in prediction:
                shadows['wally'] = False
            if "winter" in prediction:
                shadows['wally'] = True
    result = {'year': year,
              'locations': {}}
    for wp in whistle_pigs:
        result[f"shadow_{wp}"] = shadows[wp]

    # read summary table
    last_table = soup.find_all('table', attrs={'style': "border:2px solid #336699;font-size:small;"})[-1].find_next('table')
    df = pd.read_html(str(last_table).replace('° F', ''), header=0, index_col=0)[0]
    df.dropna(inplace=True) # ignore blank rows
    df.loc['metro mean'] = df.mean()

    # grade groundhog predictions
    for location in df.index.values:
        temp_delta = df.loc[location]['Temperature Difference']
        result['locations'][location] = {'mean_delta_from_norm': temp_delta}
        for wp in whistle_pigs:
            result['locations'][location][f"grade_{wp}"] = grade(temp_delta, shadows[wp])

    return(result)

def grade(delta, shadow):
    '''
    Pass/Fail grade on prediction based on observed temps variation from norm
    :param delta: mean temp difference from normal
    :param shadow: did the whistle pig see his shadow, True predicts colder temps, False warmer
    :return:
    '''
    grade = 'unknown'
    if shadow is None:
        grade = 'unknown'
    elif delta == 0:
        grade = "Push"
    elif shadow: # colder temps predicted
        if delta > 0: #warmer temps observed
           grade = "Fail"
        elif delta < 0:
            grade = "Pass"
    elif not shadow: # warmer temps predicted
        if delta > 0:  # warmer temps observed
            grade = "Pass"
        elif delta < 0:
            grade = "Fail"
    return grade

def scorecard():
    # init
    at_bats = dict()
    for wp in whistle_pigs:
        at_bats[wp] = dict()
    agreement_record = []
    for year in range(2000, 2020):
        data = get_nc_climate_office_page(year)
        observations = []

        for wp in whistle_pigs:
            if data[f"shadow_{wp}"] is not None:
                observations.append(data[f"shadow_{wp}"])
            for location in data['locations']:
                if location not in at_bats[wp].keys():
                    at_bats[wp][location] = []
                if data['locations'][location][f'grade_{wp}'] == 'Pass':
                    at_bats[wp][location].append(1)
                if data['locations'][location][f'grade_{wp}'] == 'Fail':
                    at_bats[wp][location].append(0)
        if len(set(observations)) == 1:
            agreement_record.append(1)
        else:
            agreement_record.append(0)


    print(f"location             ", end='')
    for wp in whistle_pigs:
        print(f"{wp:12}", end=' ')
    print()
    for loc, v in at_bats[whistle_pigs[0]].items():
        print(f"{loc:20}", end='')
        for wp in whistle_pigs:
            correct = sum(at_bats[wp][loc])
            years = len(at_bats[wp][loc])
            if years > 0:
                record = (correct / (years * 1.0)) * 100  # force float arith
                print(f" {correct:2}/{years:2} ({record:.0f}%)", end=' ')
            else:
                print(f" no data", end=' ')
        print()
    print ()
    print (f"{', '.join(whistle_pigs)} {sum(agreement_record)}/{len(agreement_record)}")

def check_cloud_cover(lat, lon, year, hour=12):
    '''
    making the wild assumption that a shadow would be seen with <50% cloud cover at noon
    :param lat:
    :param lon:
    :param year:
    :return:
    '''
    dt = datetime.datetime(year, 2, 2, hour, 0, 0, 0)
    timestamp = int(dt.strftime('%s'))
    URL = 'https://api.darksky.net/forecast/%s/%s,%s,%s?exclude=currently,daily,flags'
    r = requests.get(URL % (key_darksky, lat, lon, timestamp))
    data = r.json()
    cloudCover = None
    for obs in data['hourly']['data']:
        if obs['time'] == timestamp:
            cloudCover = obs['cloudCover']
    return cloudCover * 100, cloudCover < 0.5

class BunchOfTestCases(unittest.TestCase):
    def test_individual_year(self):
        data = get_nc_climate_office_page(2012)
        self.assertEqual(data['locations']['Raleigh']['grade_snerd'], 'Fail')

    def test_NC(self):
        scorecard()

    def test_gobblers(self):
        ''' comparing report of whether or not groundhog saw his shadow to cloud cover in Gobblers Knob PA at 7am '''
        lat = 40.93
        lon = -78.96
        for year, shadow in punxsutawney_phil_saw_his_shadow.items():
            pct, shadow_possible = check_cloud_cover(lat, lon, int(year), hour=7)
            print (f"{year} {shadow} {shadow_possible} {pct}")

    def test_garner(self):
        ''' comparing report of whether or not groundhog saw his shadow to cloud cover in Garner NC at noon '''
        lat = 35.7
        lon = -78.62
        for year, shadow in snerd_shaw_his_shadow.items():
            pct, shadow_possible = check_cloud_cover(lat, lon, int(year), hour=12)
            print (f"{year} {shadow} {shadow_possible}")



if __name__ == '__main__':
    scorecard()
