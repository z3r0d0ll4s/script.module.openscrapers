# -*- coding: utf-8 -*-
# modified by Venom for Openscrapers (updated url 4-29-2020)-switched to cfscrape

#  ..#######.########.#######.##....#..######..######.########....###...########.#######.########..######.
#  .##.....#.##.....#.##......###...#.##....#.##....#.##.....#...##.##..##.....#.##......##.....#.##....##
#  .##.....#.##.....#.##......####..#.##......##......##.....#..##...##.##.....#.##......##.....#.##......
#  .##.....#.########.######..##.##.#..######.##......########.##.....#.########.######..########..######.
#  .##.....#.##.......##......##..###.......#.##......##...##..########.##.......##......##...##........##
#  .##.....#.##.......##......##...##.##....#.##....#.##....##.##.....#.##.......##......##....##.##....##
#  ..#######.##.......#######.##....#..######..######.##.....#.##.....#.##.......#######.##.....#..######.

'''
    OpenScrapers Project
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import re

try: from urlparse import parse_qs, urljoin
except ImportError: from urllib.parse import parse_qs, urljoin
try: from urllib import urlencode, quote, unquote_plus
except ImportError: from urllib.parse import urlencode, quote, unquote_plus

from openscrapers.modules import cfscrape
from openscrapers.modules import client
from openscrapers.modules import debrid
from openscrapers.modules import source_utils
from openscrapers.modules import workers


class source:
	def __init__(self):
		self.priority = 15
		self.language = ['en']
		self.domains = ['btdb.eu']
		self.base_link = 'https://btdb.eu'
		self.search_link = '/search/%s/0/?sort=popular'
		self.min_seeders = 0 # to many items with no value but cached links

	def movie(self, imdb, title, localtitle, aliases, year):
		try:
			url = {'imdb': imdb, 'title': title, 'aliases': aliases, 'year': year}
			url = urlencode(url)
			return url
		except:
			return


	def tvshow(self, imdb, tvdb, tvshowtitle, localtvshowtitle, aliases, year):
		try:
			url = {'imdb': imdb, 'tvdb': tvdb, 'tvshowtitle': tvshowtitle, 'aliases': aliases, 'year': year}
			url = urlencode(url)
			return url
		except:
			return


	def episode(self, url, imdb, tvdb, title, premiered, season, episode):
		try:
			if url is None:
				return
			url = parse_qs(url)
			url = dict([(i, url[i][0]) if url[i] else (i, '') for i in url])
			url['title'], url['premiered'], url['season'], url['episode'] = title, premiered, season, episode
			url = urlencode(url)
			return url
		except:
			return


	def sources(self, url, hostDict, hostprDict):
		self.sources = []
		try:
			if url is None:
				return self.sources
			if debrid.status() is False:
				return self.sources

			data = parse_qs(url)
			data = dict([(i, data[i][0]) if data[i] else (i, '') for i in data])

			self.title = data['tvshowtitle'] if 'tvshowtitle' in data else data['title']
			self.title = self.title.replace('&', 'and').replace('Special Victims Unit', 'SVU')
			self.aliases = data['aliases']
			self.episode_title = data['title'] if 'tvshowtitle' in data else None
			self.hdlr = 'S%02dE%02d' % (int(data['season']), int(data['episode'])) if 'tvshowtitle' in data else data['year']
			self.year = data['year']

			query = '%s %s' % (self.title, self.hdlr)
			query = re.sub('[^A-Za-z0-9\s\.-]+', '', query)

			urls = []
			url = self.search_link % quote(query + ' -soundtrack') # filter
			url = urljoin(self.base_link, url)
			urls.append(url)
			urls.append(url + '&page=2')
			# log_utils.log('urls = %s' % urls, __name__, log_utils.LOGDEBUG)

			threads = []
			for url in urls:
				threads.append(workers.Thread(self.get_sources, url))
			[i.start() for i in threads]
			[i.join() for i in threads]
			return self.sources

		except:
			source_utils.scraper_error('BTDB')
			return self.sources


	def get_sources(self, url):
		try:
			scraper = cfscrape.create_scraper()
			r = scraper.get(url).content
			if not r:
				return
			posts = client.parseDOM(r, 'div', attrs={'class': 'media'})
			for post in posts:
				# file_name = client.parseDOM(post, 'span', attrs={'class': 'file-name'}) # file_name and &dn= differ 25% of the time.  May add check
				try:
					seeders = int(re.findall(r'Seeders\s+:\s+<strong class="text-success">([0-9]+|[0-9]+,[0-9]+)</strong>', post, re.DOTALL)[0].replace(',', ''))
					if self.min_seeders > seeders:
						return
				except:
					seeders = 0
					pass

				link = re.findall('<a href="(magnet:.+?)"', post, re.DOTALL)
				for url in link:
					url = unquote_plus(url).split('&tr')[0].replace('&amp;', '&').replace(' ', '.')
					url = source_utils.strip_non_ascii_and_unprintable(url)

					hash = re.compile('btih:(.*?)&').findall(url)[0]
					name = url.split('&dn=')[1]
					name = source_utils.clean_name(self.title, name)
					if source_utils.remove_lang(name, self.episode_title):
						continue

					if not source_utils.check_title(self.title, self.aliases, name, self.hdlr, self.year):
						continue

					# filter for episode multi packs (ex. S01E01-E17 is also returned in query)
					if self.episode_title:
						if not source_utils.filter_single_episodes(self.hdlr, name):
							continue

					quality, info = source_utils.get_release_quality(name, url)

					try:
						size = re.findall('((?:\d+\,\d+\.\d+|\d+\.\d+|\d+\,\d+|\d+)\s*(?:GB|GiB|Gb|MB|MiB|Mb))', post)[0]
						dsize, isize = source_utils._size(size)
						info.insert(0, isize)
					except:
						dsize = 0
						pass

					info = ' | '.join(info)

					self.sources.append({'source': 'torrent', 'seeders': seeders, 'hash': hash, 'name': name, 'quality': quality,
													'language': 'en', 'url': url, 'info': info, 'direct': False, 'debridonly': True, 'size': dsize})
		except:
			source_utils.scraper_error('BTDB')
			pass


	def resolve(self, url):
		return url