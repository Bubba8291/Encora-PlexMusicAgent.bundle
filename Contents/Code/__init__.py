# -*- coding: utf-8 -*-

### Imports ###
import sys                  # getdefaultencoding, getfilesystemencoding, platform, argv
import os                   # path.abspath, join, dirname
import re                   #
import inspect
import urllib2
import urllib
from   lxml    import etree #
from   io      import open  # open
import hashlib
from datetime import datetime, timedelta
import time
import json
import requests

###Mini Functions ###
def natural_sort_key     (s):  return [int(text) if text.isdigit() else text for text in re.split(re.compile('([0-9]+)'), str(s).lower())]  ### Avoid 1, 10, 2, 20... #Usage: list.sort(key=natural_sort_key), sorted(list, key=natural_sort_key)
def sanitize_path        (p):  return p if isinstance(p, unicode) else p.decode(sys.getfilesystemencoding()) ### Make sure the path is unicode, if it is not, decode using OS filesystem's encoding ###
def js_int               (i):  return int(''.join([x for x in list(i or '0') if x.isdigit()]))  # js-like parseInt - https://gist.github.com/douglasmiranda/2174255

### Return dict value if all fields exists "" otherwise (to allow .isdigit()), avoid key errors
def Dict(var, *arg, **kwarg):  #Avoid TypeError: argument of type 'NoneType' is not iterable
  """ Return the value of an (imbricated) dictionnary, return "" if doesn't exist unless "default=new_value" specified as end argument
      Ex: Dict(variable_dict, 'field1', 'field2', default = 0)
  """
  for key in arg:
    if isinstance(var, dict) and key and key in var or isinstance(var, list) and isinstance(key, int) and 0<=key<len(var):  var = var[key]
    else:  return kwarg['default'] if kwarg and 'default' in kwarg else ""   # Allow Dict(var, tvdbid).isdigit() for example
  return kwarg['default'] if var in (None, '', 'N/A', 'null') and kwarg and 'default' in kwarg else "" if var in (None, '', 'N/A', 'null') else var

# Function to parse ISO 8601 date string and handle 'Z' for UTC
def parse_iso8601(nft_date):
    if nft_date.endswith('Z'):
        nft_date = nft_date[:-1]  # Remove the 'Z'
        return datetime.strptime(nft_date, '%Y-%m-%dT%H:%M:%S.%f')  # Parse the datetime string
    return None  # Return None if the format is unexpected

def format_date(data):
    replace_char = Prefs['date_replace_char']
    if (len(replace_char) > 1): 
        replace_char = replace_char[0]
    replace_char = replace_char * 2
    date_info = data.get('date', {})
    full_date = ""
    iso_date = ""
    usa_date = ""
    numeric_date = ""
    
    if date_info.get('day_known') is False:
        if date_info.get('month_known') is False:
            full_date = date_info.get('full_date')[:4]  # Return YYYY
            iso_date = "{}-{}-{}".format(date_info.get('full_date')[:4], replace_char, replace_char)  # Return YYYY-xx-xx
            usa_date = "{}-{}-{}".format(replace_char, replace_char, date_info.get('full_date')[:4])  # Return xx-xx-YYYY
            numeric_date = "{}-{}-{}".format(replace_char, replace_char, date_info.get('full_date')[:4])  # Return xx-xx-YYYY
        else:
            month = date_info.get('full_date')[5:7]
            full_date = "{}, {}".format(month_name(int(month)), date_info.get('full_date')[:4])  # Return Month, YYYY
            iso_date = "{}-{}-{}".format(date_info.get('full_date')[:4], month, replace_char)  # Return YYYY-MM-xx
            usa_date = "{}-{}-{}".format(month, replace_char, date_info.get('full_date')[:4])  # Return MM-xx-YYYY
            numeric_date = "{}-{}-{}".format(replace_char, month, date_info.get('full_date')[:4])  # Return xx-MM-YYYY
    else:
        try:
            full_date = datetime.strptime(date_info.get('full_date'), "%Y-%m-%d").strftime("%B %d, %Y").replace(" 0", " ")
            iso_date = date_info.get('full_date')
            usa_date = datetime.strptime(date_info.get('full_date'), "%Y-%m-%d").strftime("%m-%d-%Y")
            numeric_date = datetime.strptime(date_info.get('full_date'), "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError as e:
            log(u'Date format error: {}'.format(e))
        except Exception as e:
            log(u'An unexpected error occurred: {}'.format(e))
    
    date_variant = date_info.get('date_variant')
    variant = " ({})".format(date_variant) if date_variant else ""    

    return {
        'full_date': full_date + variant,
        'iso': iso_date + variant,
        'usa': usa_date + variant,
        'numeric': numeric_date + variant
    }

# Used for the preference to define the format of Plex Titles
def format_title(template, data):    
    date = format_date(data)
    title = template
    title = title.replace('{show}', data.get('show', ''))
    title = title.replace('{tour}', data.get('tour', ''))
    title = title.replace('{date}', date['full_date'])
    title = title.replace('{date_iso}', date['iso'])
    title = title.replace('{date_usa}', date['usa'])
    title = title.replace('{date_numeric}', date['numeric'])
    title = title.replace('{master}', data.get('master', ''))
    title = title.replace(' - Part One', '')
    title = title.replace(' - Part 1', '')
    title = title.replace(' - Part I', '')
    title = title.replace(' - Part Two', '')
    title = title.replace(' - Part 2', '')
    title = title.replace(' - Part II', '')
    return title

def month_name(month):
    # Return the full name of the month
    return [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ][month]

def clean_html_description(html_description):
    # Preserve line breaks
    text = re.sub(r'</p>', '\n', html_description)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Manually replace common HTML entities
    text = text.replace('&#039;', "'")
    text = text.replace('&quot;', '"')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    return text

### Get media root folder ###
def GetLibraryRootPath(dir):
  library, root, path = '', '', ''
  for root in [os.sep.join(dir.split(os.sep)[0:x+2]) for x in range(0, dir.count(os.sep))]:
    if root in PLEX_LIBRARY:
      library = PLEX_LIBRARY[root]
      path    = os.path.relpath(dir, root)
      break
  else:  #401 no right to list libraries (windows)
    log(u'Library access denied')
    filename = os.path.join(CachePath, '_Logs', '_root_.scanner.log')
    if os.path.isfile(filename):
      log(u'ASS root scanner file present: "{}"'.format(filename))
      line = Core.storage.load(filename)  #with open(filename, 'rb') as file:  line=file.read()
      for root in [os.sep.join(dir.split(os.sep)[0:x+2]) for x in range(dir.count(os.sep)-1, -1, -1)]:
        if "root: '{}'".format(root) in line:  path = os.path.relpath(dir, root).rstrip('.');  break  #Log.Info(u'[!] root not found: "{}"'.format(root))
      else: path, root = '_unknown_folder', ''
    else:  log(u'ASS root scanner file missing: "{}"'.format(filename))
  return library, root, path


#> called when looking for encora API Key
def encora_api_key():
  path = os.path.join(PluginDir, "encora-key.txt")
  if os.path.isfile(path):
    value = Data.Load(path)
    if value:
      value = value.strip()
    if value:
    #   Log.Debug(u"Loaded token from encora-token.txt file")

      return value

  # Fall back to Library preference
  return Prefs['encora_api_key']

#> called when looking for stagemedia API Key
def stagemedia_api_key():
  path = os.path.join(PluginDir, "stagemedia-key.txt")
  if os.path.isfile(path):
    value = Data.Load(path)
    if value:
      value = value.strip()
    if value:
    #   log(u"Loaded token from stagemedia-token.txt file")

      return value

  # Fall back to Library preference
  return Prefs['stagemedia_api_key']

def make_request(url, headers={}):
    # Initialize variables
    response = None
    str_error = None

    sleep_time = 1
    num_retries = 4
    for x in range(0, num_retries):
        log('Requesting: {}'.format(url))
        try:
            response = requests.get(url, headers=headers, timeout=90, verify=False)
        except Exception as str_error:
            log('Failed HTTP request: {} | {}'.format(x, url))
            log('{}'.format(str_error))

        if str_error:
            time.sleep(sleep_time)
            sleep_time = sleep_time * x
        else:
            break

    return response.content if response else response

###
def json_load(template, *args):
    url = template.format(*args)
    url = sanitize_path(url)
    iteration = 0
    json_page = {}
    json_data = {}


    # Bearer token
    headers = {
        'Authorization': 'Bearer {}'.format(encora_api_key())  # Use the bearer token
    }

    while not json_data or Dict(json_page, 'next_page_url') and Dict(json_page, 'per_page') != 1 and iteration < 50:
        try:
            full_url = Dict(json_page, 'next_page_url') if Dict(json_page, 'next_page_url') else url
            json_page = JSON.ObjectFromURL(full_url, headers=headers)  # Pass headers to the request
        except Exception as e:
            json_data = JSON.ObjectFromString(e.content)
            raise ValueError('code: {}, message: {}'.format(Dict(json_data, 'error', 'code'), Dict(json_data, 'error', 'message')))

        if json_data:
            json_data['data'].extend(json_page['data'])
        else:
            json_data = json_page
        
        iteration += 1

    if Dict(json_data, 'data'):
        fixed_json_data = []
        for data in json_data['data']:
            fixed_json_data.append(data['recording'])
        json_data['data'] = fixed_json_data

    return json_data

def find_encora_id_file(directory):
    pattern = re.compile(r'\.encora-a-(\d+)')
    
    for filename in os.listdir(directory):
        match = pattern.match(filename)
        if match:
            return match.group(1)
    
    # If no match found, check for .encora-a-id file
    encora_id_file = os.path.join(directory, '.encora-a-id')
    if os.path.isfile(encora_id_file):
        with open(encora_id_file, 'r') as file:
            return file.read().strip()
    
    return None
    
def Start():
  #HTTP.CacheTime                  = CACHE_1DAY
  HTTP.Headers['User-Agent'     ] = 'PlexAgent/0.9'
  HTTP.Headers['Accept-Language'] = 'en-us'
  if not os.path.isfile(COLLECTION_FILE):
    updateCollectionData()

def clean_path(path):
    try:
        path = sanitize_path(path)
    except Exception as e:
        log('search() - Exception1: filename: "{}", e: "{}"'.format(path, e))
    try:
        path = os.path.basename(path)
    except Exception as e:
        log('search() - Exception2: filename: "{}", e: "{}"'.format(path, e))
    try:
        path = urllib2.unquote(path)
    except Exception as e:
        log('search() - Exception3: filename: "{}", e: "{}"'.format(path, e))
    return path

### Assign unique ID ###
def Search(results, media, lang, manual):
    filename = clean_path(media.filename)
    album = media.name if media.name else media.album if media.album else None

    collection = getCollectionData()
    collection = [item for item in collection['data']]

    if filename:
        dir = os.path.dirname(filename)
        log(u'Search() - dir: {}'.format(dir))
        log(u'Search() - filename: {}'.format(filename))

        # Extract recording ID from the folder name
        folder_name = os.path.basename(dir)
        # Try to find the recording ID from folder name
        recording_id_match = re.search(r'e-(\d+)', dir)
        if recording_id_match:
            recording_id = recording_id_match.group(1)
            log(u'search() - Found recording ID in folder name: {}'.format(recording_id))
        else:
            # Fallback to checking for .encora_{id} file inside the folder

            recording_id = find_encora_id_file(dir)
            if recording_id:
                log(u'search() - Found recording ID in filename: {}'.format(recording_id))
            else:
                log(u'search() - No recording ID found in filenames')
        log(u'Found recording ID: {}'.format(recording_id))
        if recording_id:
            try:
                json_recording_details = get_first([item for item in collection if str(item.get('id')) == recording_id])
                if json_recording_details:
                    log(u'filename: "{}", title: "{}"'.format(filename, json_recording_details['show']))
                    results.Append(MetadataSearchResult(
                        id='encoramusic|{}|{}'.format(recording_id, os.path.basename(dir)),
                        name=json_recording_details['show'],
                        year=Datetime.ParseDate(json_recording_details['date']['full_date']).year,
                        score=100,
                        lang=lang
                    ))
                    log(u''.ljust(157, '='))
                    return
            except Exception as e:
                log(u'search() - Could not retrieve data from Encora API for: "{}", Exception: "{}"'.format(recording_id, e))

        # If no recording ID is found, log and return a default result
        # log(u'search() - No recording ID found in folder name: "{}"'.format(folder_name))
        # library, root, path = GetLibraryRootPath(dir)
        # log(u'Putting folder name "{}" as guid since no assigned recording ID was found'.format(path.split(os.sep)[-1]))
        # results.Append(MetadataSearchResult(
        #     id='encoramusic|{}|{}'.format(path.split(os.sep)[-2] if os.sep in path else '', dir),
        #     name=os.path.basename(dir),
        #     year=None,
        #     score=80,
        #     lang=lang
        # ))
        # log(''.ljust(157, '='))
    else:
        if album and album == '[Unknown Album]':
            return
        log(u'Search() - No filename found. Searching for album: {}'.format(album))
        find_in_collection = [item for item in collection if item.get('show') in album or album in item.get('show') or item.get('date').get('full_date')[:4] in album]
        # if year:
            # find_in_collection = [item for item in find_in_collection if item.get('date').get('full_date')[:4] == year]
        log(u'Found {} albums in collection'.format(len(find_in_collection)))
        for item in find_in_collection:
            log(u'Found album in collection: {}'.format(item.get('show')))
            display_name = format_title(Prefs['title_format'], item)
            results.Append(MetadataSearchResult(
                id='encoramusic|{}|{}'.format(item.get('id'), ''),
                name=display_name,
                year=Datetime.ParseDate(item.get('date').get('full_date')).year,
                score=100,
                lang=lang
            ))
        return

def SearchArtist(results, media, lang, manual):
    filename = clean_path(media.filename)
    artist = media.artist if media.artist else None

    collection = getCollectionData()
    collection = [item for item in collection['data']]

    if filename:
        dir = os.path.dirname(filename)
        log(u'Search() - dir: {}'.format(dir))
        log(u'Search() - filename: {}'.format(filename))

        # Extract recording ID from the folder name
        folder_name = os.path.basename(dir)
        # Try to find the recording ID from folder name
        recording_id_match = re.search(r'e-(\d+)', dir)
        if recording_id_match:
            recording_id = recording_id_match.group(1)
            log(u'search() - Found recording ID in folder name: {}'.format(recording_id))
        else:
            # Fallback to checking for .encora_{id} file inside the folder

            recording_id = find_encora_id_file(dir)
            if recording_id:
                log(u'search() - Found recording ID in filename: {}'.format(recording_id))
            else:
                log(u'search() - No recording ID found in filenames')
    else:
        if artist and artist == '[Unknown Artist]':
            return
        log(u'Search() - No filename found. Searching for artist: {}'.format(artist))
        find_in_collection = [item['master'] for item in collection if item.get('master') in artist or artist in item.get('master')]
        unique_albums = list(set(find_in_collection))
        # if year:
            # find_in_collection = [item for item in find_in_collection if item.get('date').get('full_date')[:4] == year]
        log(u'Found {} albums in collection'.format(len(unique_albums)))
        for master in unique_albums:
            log(u'Found artist in collection: {}'.format(master))
            results.Append(MetadataSearchResult(
                id='encoramusic-artist|{}'.format(master),
                name=master,
                score=100,
                lang=lang
            ))
        return
    if recording_id:
        try:
            json_recording_details = get_first([item for item in collection if str(item.get('id')) == recording_id])
            if json_recording_details:
                master = json_recording_details['master']
                log(u'filename: "{}", master: "{}"'.format(filename, master))
                results.Append(MetadataSearchResult(
                    id='encoramusic-artist|{}'.format(master),
                    name=master,
                    score=100,
                    lang=lang
                ))
                log(u''.ljust(157, '='))
                return
        except Exception as e:
            log(u'search() - Could not retrieve data from Encora API for: "{}", Exception: "{}"'.format(recording_id, e))

    # If no recording ID is found, log and return a default result
    log(u'search() - No recording ID found in folder name: "{}"'.format(folder_name))
    library, root, path = GetLibraryRootPath(dir)
    log(u'Putting folder name "{}" as guid since no assigned recording ID was found'.format(path.split(os.sep)[-1]))
    results.Append(MetadataSearchResult(
        id='encoramusic-artist|{}'.format(path.split(os.sep)[-2] if os.sep in path else ''),
        name=os.path.basename(dir),
        score=80,
        lang=lang
    ))
    log(''.ljust(157, '='))

### Download metadata using encora ID ###
def Update(metadata, media, lang, force):
    log(u'=== update(lang={}, force={}) ==='.format(lang, force))
    temp1, recording_id, folder = metadata.id.split("|")

    log(u''.ljust(157, '='))

    collection = getCollectionData()
    collection = [item for item in collection['data']]

    try:
        json_recording_details = get_first([item for item in collection if str(item.get('id')) == recording_id])
        if json_recording_details:
            log(u'Setting metadata for recording ID: {}'.format(recording_id))
            # Update metadata fields based on the Encora API response
            metadata.title = format_title(Prefs['title_format'], json_recording_details)
            metadata.original_title = json_recording_details['show']
            metadata.originally_available_at = (datetime.strptime(json_recording_details['date']['full_date'], "%Y-%m-%d") + timedelta(days=1)).date()
            metadata.studio = json_recording_details['tour']
            show_description_html = json_recording_details.get('metadata', {}).get('show_description', 'Not provided. Edit the show on Encora to populate this!')
            show_description = clean_html_description(show_description_html)
            metadata.summary = show_description
            log(u'artist: {}'.format(metadata.artist))
            #log updated metadata
            log(u'Updated metadata for recording ID: {}'.format(recording_id))
            log(u'title: {}'.format(metadata.title))
            log(u'original_title: {}'.format(metadata.original_title))
            log(u'originally_available_at: {}'.format(metadata.originally_available_at))
            log(u'studio: {}'.format(metadata.studio))
            log(u'summary: {}'.format(metadata.summary))

            if Prefs['create_show_collections']: 
                metadata.collections.add(json_recording_details["show"])

            # Set content rating based on NFT status
            nft_date = json_recording_details['nft']['nft_date']
            nft_forever = json_recording_details['nft']['nft_forever']

            # Parse the nft_date in ISO 8601 format
            nft_date_parsed = parse_iso8601(nft_date) if nft_date else None

            # Get the current time in UTC (naive datetime)
            current_time = datetime.utcnow()

            # Compare only when nft_date is present and properly parsed
            if (nft_forever or (nft_date_parsed and nft_date_parsed > current_time)):
                labels = metadata.labels.new()
                labels.name = 'NFT'

            # Create a cast array
            cast_array = json_recording_details['cast']
            show_id = json_recording_details['metadata']['show_id']

            ## Prepare media db api query 
            ## TODO: Fix url once API is ready
            media_db_api_url = "https://stagemedia.me/api/images?show_id={}&actor_ids={}".format(show_id, ','.join([str(x['performer']['id']) for x in cast_array]))
            log(u'Media DB API URL: {}'.format(media_db_api_url))
            ## make request to mediadb for poster / headshots
            headers = {
                'Authorization': 'Bearer {}'.format(stagemedia_api_key()),
                'User-Agent': 'PlexAgent/0.9'
            }
            request = urllib2.Request(media_db_api_url, headers=headers)
            response = urllib2.urlopen(request)
            api_response = json.load(response)
            log('Media DB API response: {}'.format(api_response))

            # Update genres based on recording type
            metadata.genres.clear()
            recording_type = json_recording_details['metadata']['recording_type']
            if recording_type:
                metadata.genres.add(recording_type)
            if json_recording_details['metadata']['media_type']:
                metadata.genres.add(json_recording_details['metadata']['media_type'])
                log(u'added genre {}'.format(json_recording_details['metadata']['media_type']))

            def get_order(cast_member):
                return cast_member['character'].get('order', 999) if cast_member['character'] else 999

            performer_url_map = {performer['id']: performer['url'] for performer in api_response['performers']}

            for key in metadata.posters.keys():
                del metadata.posters[key]

            # set the posters from API
            if 'posters' in api_response:
                for full_poster_url in api_response['posters']:
                    # log each URL
                    log(u'Full Poster URL: {}'.format(full_poster_url))
                    metadata.posters[full_poster_url] = Proxy.Preview(HTTP.Request(full_poster_url).content)

            sorted_cast = sorted(json_recording_details['cast'], key=get_order)
            # cast_names = [x['performer']['name'] for x in sorted_cast]

            return
    except Exception as e:
        log(u'update() - Could not retrieve data from Encora API for: "{}", Exception: "{}"'.format(recording_id, e))

    log('=== End Of Agent Call, errors after that are Plex related ==='.ljust(157, '='))

def UpdateArtist(metadata, media, lang, force):
    log(u'=== update(lang={}, force={}) ==='.format(lang, force))
    temp1, master = metadata.id.split("|")

    metadata.title = master
    metadata.rating = '10'
    return

def log(message, debug=False):
    if debug:
        Log.Debug(u'{}'.format(message))
    else:
        Log(u'{}'.format(message))

def get_first(iterable, default=None):
    if iterable:
        for item in iterable:
            return item
    return default

def saveCollectionData(collection_data):
    # Save the collection data
    Data.SaveObject(COLLECTION_FILE, collection_data)

def updateCollectionData():
    # Get the collection data
    collection_data = json_load(ENCORA_API_COLLECTION)
    # Save the collection data
    saveCollectionData(collection_data)
    return collection_data

def getCollectionData():
    if os.path.isfile(COLLECTION_FILE):
        # Load the collection data
        collection_data = Data.LoadObject(COLLECTION_FILE)
        return collection_data
    # Update the collection data
    collection_data = updateCollectionData()
    return collection_data

### Agent declaration ##################################################################################################################################################
class EncoraMusicAlbum(Agent.Album):
  name, primary_provider, fallback_agent, contributes_to, accepts_from, languages = 'EncoraMusic', True, ['com.plexapp.agents.xbmcnfo'], None, ['com.plexapp.agents.xbmcnfo'], [Locale.Language.NoLanguage]
  def search (self, results, media, lang, manual):  Search (results,  media, lang, manual)
  def update (self, metadata, media, lang, force ):  Update (metadata, media, lang, force)

class EncoraMusicArtist(Agent.Artist):
  name, primary_provider, fallback_agent, contributes_to, accepts_from, languages = 'EncoraMusic', True, ['com.plexapp.agents.xbmcnfo'], None, ['com.plexapp.agents.xbmcnfo'], [Locale.Language.NoLanguage]
  def search (self, results, media, lang, manual):  SearchArtist (results,  media, lang, manual)
#   def update (self, metadata, media, lang, force ):  UpdateArtist (metadata, media, lang, force)


### Variables ###
PluginDir                = os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), "..", ".."))
PlexRoot                 = os.path.abspath(os.path.join(PluginDir, "..", ".."))
CachePath                = os.path.join(PlexRoot, "Plug-in Support", "Data", "com.plexapp.agents.encora-music", "DataItems")
PLEX_LIBRARY             = {}
PLEX_LIBRARY_URL         = "http://127.0.0.1:32400/library/sections/"    # Allow to get the library name to get a log per library https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token
ENCORA_API_BASE_URL      = "https://encora.it/api/"
ENCORA_API_COLLECTION    = ENCORA_API_BASE_URL + "collection"  # fetch collection data
ENCORA_API_RECORDING_INFO= ENCORA_API_BASE_URL + 'recording/{}' # fetch recording data
COLLECTION_FILE = os.path.join(CachePath, 'collection.json')


### Plex Library XML ###
Log.Info(u"Library: "+PlexRoot)  #Log.Info(file)
token_file_path = os.path.join(PlexRoot, "X-Plex-Token.id")
if os.path.isfile(token_file_path):
  Log.Info(u"'X-Plex-Token.id' file present")
  token_file=Data.Load(token_file_path)
  if token_file:  PLEX_LIBRARY_URL += "?X-Plex-Token=" + token_file.strip()
try:
  library_xml = etree.fromstring(urllib2.urlopen(PLEX_LIBRARY_URL).read())
  for library in library_xml.iterchildren('Directory'):
    for path in library.iterchildren('Location'):
      PLEX_LIBRARY[path.get("path")] = library.get("title")
      Log.Info(u"{} = {}".format(path.get("path"), library.get("title")))
except Exception as e:  Log.Info(u"Place correct Plex token in {} file or in PLEX_LIBRARY_URL variable in Code/__init__.py to have a log per library - https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token, Error: {}".format(token_file_path, str(e)))
