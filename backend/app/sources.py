# Curated source list, v8.
#
# Sources in this version are drawn from:
#   - IRONSIGHT (github.com/NoblerWorks-HQ/IRONSIGHT) — verified July 2026
#   - OSINT War Room (github.com/Hue-Jhan/OSINT-War-Room)
#   - Meridian Intel (github.com/sumsumai/meridian-intel)
#   - OSINTmonitor (github.com/marcko80/osintmonitor)
#   - FeedSpot Top 60 Defense RSS (rss.feedspot.com/defense_rss_feeds/)
#   - Manual curation and cross-checking
#
# reliability tiers:
#   "official"             government, military, or NATO/EU institutional
#   "established_media"    mainstream national/international news orgs
#   "regional_specialist"  think tanks, specialist outlets with deep focus
#   "unverified"           social/Telegram accounts, individual OSINT trackers
#
# Note on Russian/pro-Russian Telegram channels: these are included
# deliberately as SIGNAL on Russian information operations and narrative
# management, not as factual ground truth. They are tagged "unverified"
# and the analyst brief prompts explicitly hedge language for unverified
# sources. Include them, read them skeptically, compare against
# Ukrainian/Western sources for each claim.
#
# kind: "rss" | "social" | "github" | "telegram" | "twitter"

from urllib.parse import quote_plus


def _google_news(query: str, locale: str = "GB") -> str:
    """Build a stable English Google News RSS bridge for sites without feeds."""
    language = "en-US" if locale == "US" else "en-GB"
    return (
        f"https://news.google.com/rss/search?q={quote_plus(query)}"
        f"&hl={language}&gl={locale}&ceid={locale}:en"
    )

SOURCES = [

    # ---------------------------------------------------------------
    # Legacy northern-Europe collection pack. The normalisation block below
    # routes each source into AO_HIGH_NORTH, AO_EUROPE or GLOBAL.
    # Russian hybrid, grey-zone, EW, sabotage, espionage focus
    # ---------------------------------------------------------------

    # Regional specialist RSS
    {"name": "The Baltic Times", "kind": "rss",
     "url_or_handle": "https://www.baltictimes.com/rss/",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Latvian Public Media (LSM English)", "kind": "rss",
     "url_or_handle": "https://eng.lsm.lv/rss/",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Radio Sweden English", "kind": "rss",
     "url_or_handle": "https://api.sr.se/api/rss/program/2054?format=145",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Norway's News in English (newsinenglish.no)", "kind": "rss",
     "url_or_handle": "https://www.newsinenglish.no/feed/",
     "ao": "AO_NORTH", "reliability": "established_media"},

    # Defense/military specialist RSS
    {"name": "European Defence Review", "kind": "rss",
     "url_or_handle": "https://www.edrmagazine.eu/feed",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Defense One", "kind": "rss",
     "url_or_handle": "https://www.defenseone.com/rss/all/",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "RealClearDefense", "kind": "rss",
     "url_or_handle": "https://www.realcleardefense.com/index.xml",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Defence Blog", "kind": "rss",
     "url_or_handle": "https://defence-blog.com/feed",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "UK Defence Journal", "kind": "rss",
     "url_or_handle": "https://ukdefencejournal.org.uk/feed/",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Breaking Defense", "kind": "rss",
     "url_or_handle": "https://breakingdefense.com/feed/",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "War on the Rocks", "kind": "rss",
     "url_or_handle": "https://warontherocks.com/feed/",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Task & Purpose", "kind": "rss",
     "url_or_handle": "https://taskandpurpose.com/feed/",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Military Watch Magazine", "kind": "rss",
     "url_or_handle": "https://militarywatchmagazine.com/feeds/headlines.xml",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},

    # Established media (European/North)
    {"name": "BBC World - Europe", "kind": "rss",
     "url_or_handle": "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Kyiv Independent", "kind": "rss",
     "url_or_handle": "https://kyivindependent.com/news-archive/?format=rss",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "The Moscow Times (independent)", "kind": "rss",
     "url_or_handle": "https://www.themoscowtimes.com/rss/news",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Meduza (English)", "kind": "rss",
     "url_or_handle": "https://meduza.io/rss/en/all",
     "ao": "AO_NORTH", "reliability": "established_media"},

    {"name": "Euromaidan Press", "kind": "rss",
     "url_or_handle": "https://euromaidanpress.com/feed/",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Ukrainska Pravda (English)", "kind": "rss",
     "url_or_handle": "https://www.pravda.com.ua/eng/rss/",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "The Insider (independent RU)", "kind": "rss",
     "url_or_handle": "https://theins.ru/feed",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},

    # Replacements for blocked/dead sources — all confirmed live from
    # RFE/RL's own RSS page (rferl.org/rssfeeds) and Substack
    {"name": "Jamestown Foundation (Substack)", "kind": "rss",
     "url_or_handle": "https://jamestown.substack.com/feed",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "RFE/RL - Russia", "kind": "rss",
     "url_or_handle": "https://www.rferl.org/api/zpiirl-vomx-tpe_gmr",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "RFE/RL - Ukraine", "kind": "rss",
     "url_or_handle": "https://www.rferl.org/api/zviipl-vomx-tpeugmm",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "RFE/RL - Belarus", "kind": "rss",
     "url_or_handle": "https://www.rferl.org/api/zgoiql-vomx-tpe-kmo",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "RFE/RL - Russia Invades Ukraine", "kind": "rss",
     "url_or_handle": "https://www.rferl.org/api/zbgvmtl-vomx-tpeq_kmr",
     "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "RFE/RL - Middle East", "kind": "rss",
     "url_or_handle": "https://www.rferl.org/api/zigkmtl-vomx-tpemm-mr",
     "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "RFE/RL - Iran (Farda)", "kind": "rss",
     "url_or_handle": "https://www.rferl.org/api/z-oiil-vomx-tpergmp",
     "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "RAND Corporation - National Security", "kind": "rss",
     "url_or_handle": "https://www.rand.org/topics/national-security.xml",
     "ao": "GLOBAL", "reliability": "regional_specialist"},
    {"name": "CSIS - Center for Strategic & International Studies", "kind": "rss",
     "url_or_handle": "https://www.csis.org/rss.xml",
     "ao": "GLOBAL", "reliability": "regional_specialist"},
    {"name": "Wilson Center - Russia/Eurasia", "kind": "rss",
     "url_or_handle": "https://www.wilsoncenter.org/rss/kennan",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Atlantic Council - Europe", "kind": "rss",
     "url_or_handle": "https://www.atlanticcouncil.org/category/issue/europe/feed/",
     "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Atlantic Council - Middle East", "kind": "rss",
     "url_or_handle": "https://www.atlanticcouncil.org/category/region/middle-east/feed/",
     "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "i24NEWS (Israel)", "kind": "rss",
     "url_or_handle": "https://www.i24news.tv/en/rss",
     "ao": "AO_LEVANT", "reliability": "established_media"},

    # ---------------------------------------------------------------
    # AO_LEVANT — Broader Middle East, Lebanon / Jordan focus
    # ---------------------------------------------------------------

    # Established media
    {"name": "Al Jazeera - All", "kind": "rss",
     "url_or_handle": "https://www.aljazeera.com/xml/rss/all.xml",
     "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Jerusalem Post", "kind": "rss",
     "url_or_handle": "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
     "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "BBC World - Middle East", "kind": "rss",
     "url_or_handle": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
     "ao": "AO_LEVANT", "reliability": "established_media"},

    # Regional specialist
    {"name": "Middle East Eye", "kind": "rss",
     "url_or_handle": "https://www.middleeasteye.net/rss",
     "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Long War Journal", "kind": "rss",
     "url_or_handle": "https://www.longwarjournal.org/feed",
     "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Al-Monitor", "kind": "rss",
     "url_or_handle": "https://www.al-monitor.com/rss",
     "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Middle East Institute", "kind": "rss",
     "url_or_handle": "https://www.mei.edu/rss.xml",
     "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Syria Comment (Joshua Landis)", "kind": "rss",
     "url_or_handle": "https://feeds.feedburner.com/Syriacomment",
     "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Drop Site News", "kind": "rss",
     "url_or_handle": "https://www.dropsitenews.com/feed",
     "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "The Cradle", "kind": "rss",
     "url_or_handle": "https://thecradle.co/feed",
     "ao": "AO_LEVANT", "reliability": "regional_specialist"},

    # ---------------------------------------------------------------
    # GLOBAL — wires that cover both AOs meaningfully
    # ---------------------------------------------------------------
    {"name": "The Guardian - World", "kind": "rss",
     "url_or_handle": "https://www.theguardian.com/world/rss",
     "ao": "GLOBAL", "reliability": "established_media"},
    {"name": "BBC World News", "kind": "rss",
     "url_or_handle": "https://feeds.bbci.co.uk/news/world/rss.xml",
     "ao": "GLOBAL", "reliability": "established_media"},
    {"name": "New York Times - World", "kind": "rss",
     "url_or_handle": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
     "ao": "GLOBAL", "reliability": "established_media"},
    {"name": "France24 English", "kind": "rss",
     "url_or_handle": "https://www.france24.com/en/rss",
     "ao": "GLOBAL", "reliability": "established_media"},
    {"name": "Wall Street Journal - World", "kind": "rss",
     "url_or_handle": "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
     "ao": "GLOBAL", "reliability": "established_media"},
    {"name": "U.S. Department of Defense News", "kind": "rss",
     "url_or_handle": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945&max=10",
     "ao": "GLOBAL", "reliability": "official"},
    {"name": "Bellingcat", "kind": "rss",
     "url_or_handle": "https://www.bellingcat.com/feed/",
     "ao": "GLOBAL", "reliability": "regional_specialist"},
    {"name": "Foreign Policy", "kind": "rss",
     "url_or_handle": "https://foreignpolicy.com/feed/",
     "ao": "GLOBAL", "reliability": "regional_specialist"},

    # ---------------------------------------------------------------
    # Telegram — public channels
    # Iran/Israel/Levant theater (from IRONSIGHT verified list)
    # ---------------------------------------------------------------
    {"name": "Al Jazeera English (Telegram)", "kind": "telegram",
     "url_or_handle": "AJEnglish", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "OSINTdefender (Telegram)", "kind": "telegram",
     "url_or_handle": "OSINTdefender", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "Faytuks News (Telegram)", "kind": "telegram",
     "url_or_handle": "Faytuks", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "Warfare Analysis (Telegram)", "kind": "telegram",
     "url_or_handle": "warfareanalysis", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "Quds News Network (Telegram)", "kind": "telegram",
     "url_or_handle": "QudsNen", "ao": "AO_LEVANT", "reliability": "unverified"},
    {"name": "Iran International (Telegram)", "kind": "telegram",
     "url_or_handle": "IranIntl_En", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Times of Israel (Telegram)", "kind": "telegram",
     "url_or_handle": "timesofisrael", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Drop Site News (Telegram)", "kind": "telegram",
     "url_or_handle": "dropsitenews", "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "The Cradle (Telegram)", "kind": "telegram",
     "url_or_handle": "TheCradleMedia", "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "ME Spectator (Telegram)", "kind": "telegram",
     "url_or_handle": "MESpectator", "ao": "AO_LEVANT", "reliability": "unverified"},

    # Russia/Ukraine/Baltics theater (from IRONSIGHT verified list, July 2026)
    # Ukrainian official/military
    {"name": "Ukraine General Staff (Telegram)", "kind": "telegram",
     "url_or_handle": "GeneralStaffZSU", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Ukraine Air Force (Telegram)", "kind": "telegram",
     "url_or_handle": "kpszsu", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Defense Intelligence of Ukraine (Telegram)", "kind": "telegram",
     "url_or_handle": "DIUkraine", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Ukraine NOW (Telegram)", "kind": "telegram",
     "url_or_handle": "ukrainenow", "ao": "AO_NORTH", "reliability": "established_media"},
    # Ukrainian OSINT/news
    {"name": "Kyiv Independent (Telegram)", "kind": "telegram",
     "url_or_handle": "kyivindependent", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "NEXTA (Telegram)", "kind": "telegram",
     "url_or_handle": "nexta_live", "ao": "AO_NORTH", "reliability": "unverified"},
    {"name": "Insider UA (Telegram)", "kind": "telegram",
     "url_or_handle": "insiderUAenglish", "ao": "AO_NORTH", "reliability": "unverified"},
    # Russian state/war correspondents — pro-Russian MoD narrative signal
    {"name": "Rybar (Telegram — pro-RU narrative)", "kind": "telegram",
     "url_or_handle": "rybar", "ao": "AO_NORTH", "reliability": "unverified"},
    {"name": "WarGonzo (Telegram — pro-RU narrative)", "kind": "telegram",
     "url_or_handle": "wargonzo", "ao": "AO_NORTH", "reliability": "unverified"},
    {"name": "Colonel Cassad (Telegram — pro-RU narrative)", "kind": "telegram",
     "url_or_handle": "boris_rozhin", "ao": "AO_NORTH", "reliability": "unverified"},
    {"name": "Grey Zone (Telegram — pro-RU narrative)", "kind": "telegram",
     "url_or_handle": "grey_zone", "ao": "AO_NORTH", "reliability": "unverified"},
    # Independent Russian journalism
    {"name": "Meduza (Telegram)", "kind": "telegram",
     "url_or_handle": "meduzaproject", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Astra (Telegram — independent RU)", "kind": "telegram",
     "url_or_handle": "astrapress", "ao": "AO_NORTH", "reliability": "unverified"},
    # Global OSINT aggregators
    {"name": "Reuters (Telegram)", "kind": "telegram",
     "url_or_handle": "Reuters", "ao": "GLOBAL", "reliability": "established_media"},
    {"name": "War Monitor (Telegram)", "kind": "telegram",
     "url_or_handle": "WarMonitor3", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "Conflicts Monitor (Telegram)", "kind": "telegram",
     "url_or_handle": "ConflictsTracker", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "LebOSINT (Telegram)", "kind": "telegram",
     "url_or_handle": "LebOSINT", "ao": "AO_LEVANT", "reliability": "unverified"},

    # ---------------------------------------------------------------
    # Twitter/X (requires TWITTER_BEARER_TOKEN)
    # ---------------------------------------------------------------
    {"name": "OSINT: Baltics watcher (X)", "kind": "twitter",
     "url_or_handle": "Baltic_Watch", "ao": "AO_NORTH", "reliability": "unverified"},
    {"name": "OSINT: Middle East watcher (X)", "kind": "twitter",
     "url_or_handle": "IntelCrab", "ao": "AO_LEVANT", "reliability": "unverified"},
]

# ---------------------------------------------------------------------------
# Expanded collection pack — validated live August 2026.
#
# Direct feeds are preferred. Where an organisation has retired or blocks RSS,
# a site-restricted Google News feed provides a resilient public bridge. Social
# and GitHub sources use their native public RSS/Atom endpoints and remain
# clearly labelled so analysts can distinguish reporting from tooling updates.
# ---------------------------------------------------------------------------
SOURCES.extend([
    # AO NORTH — regional reporting, government and hybrid-threat analysis
    {"name": "Estonian Public Broadcasting (ERR English)", "kind": "rss",
     "url_or_handle": "https://news.err.ee/rss", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Yle News (Finland)", "kind": "rss",
     "url_or_handle": "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "SVT Nyheter (Sweden)", "kind": "rss",
     "url_or_handle": "https://www.svt.se/rss.xml", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "EUvsDisinfo", "kind": "rss",
     "url_or_handle": "https://euvsdisinfo.eu/feed/", "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Traficom Finland (English)", "kind": "rss",
     "url_or_handle": "https://www.traficom.fi/feed/rss/en", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "European Commission Press Corner", "kind": "rss",
     "url_or_handle": "https://ec.europa.eu/commission/presscorner/api/rss?language=en", "ao": "GLOBAL", "reliability": "official"},
    {"name": "UN News - Europe", "kind": "rss",
     "url_or_handle": "https://news.un.org/feed/subscribe/en/news/region/europe/feed/rss.xml", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Defense News", "kind": "rss",
     "url_or_handle": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", "ao": "GLOBAL", "reliability": "regional_specialist"},
    {"name": "The War Zone", "kind": "rss",
     "url_or_handle": "https://www.twz.com/feed", "ao": "GLOBAL", "reliability": "regional_specialist"},
    {"name": "LRT English via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Alrt.lt%2Fen+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "High North News via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Ahighnorthnews.com+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Barents Observer via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Athebarentsobserver.com+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "NATO News via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Anato.int+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Hybrid CoE via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Ahybridcoe.fi&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "NATO StratCom COE via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Astratcomcoe.org&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "Finnish Defence Forces via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Apuolustusvoimat.fi+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Swedish Armed Forces via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aforsvarsmakten.se&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Baltic Infrastructure & GNSS Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Baltic+Sea+OR+Finland+OR+Estonia+OR+Latvia+OR+Lithuania%29+%28cable+OR+pipeline+OR+GPS+jamming+OR+GNSS+interference+OR+sabotage%29+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_NORTH", "reliability": "unverified"},

    # AO LEVANT — regional, multilateral and official reporting
    {"name": "International Crisis Group", "kind": "rss",
     "url_or_handle": "https://www.crisisgroup.org/rss", "ao": "GLOBAL", "reliability": "regional_specialist"},
    {"name": "IAEA Top News", "kind": "rss",
     "url_or_handle": "https://www.iaea.org/feeds/topnews", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "The Guardian - Middle East", "kind": "rss",
     "url_or_handle": "https://www.theguardian.com/world/middleeast/rss", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Arab News - Middle East", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aarabnews.com+%28Lebanon+OR+Jordan+OR+Israel+OR+Syria+OR+Iran%29+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "UN News - Middle East", "kind": "rss",
     "url_or_handle": "https://news.un.org/feed/subscribe/en/news/region/middle-east/feed/rss.xml", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "CENTCOM Releases via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Acentcom.mil+when%3A7d&hl=en-US&gl=US&ceid=US%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "UNIFIL Updates via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aunifil.unmissions.org+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Lebanese Armed Forces via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Alebarmy.gov.lb+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Jordan Armed Forces via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Ajaf.mil.jo+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Petra News Agency Jordan via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Apetra.gov.jo+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "L'Orient Today via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Atoday.lorientlejour.com+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Times of Israel via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Atimesofisrael.com+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Al Arabiya English via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aenglish.alarabiya.net+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Iran International via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Airanintl.com+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "ReliefWeb Levant via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Areliefweb.int+%28Lebanon+OR+Jordan+OR+Syria%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},

    # Public Telegram channels — official first, then explicitly-tiered OSINT
    {"name": "AFU StratCom (Telegram)", "kind": "telegram", "url_or_handle": "AFUStratCom", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Ukraine Land Forces (Telegram)", "kind": "telegram", "url_or_handle": "landforcesofukraine", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Ukraine Ministry of Defence (Telegram)", "kind": "telegram", "url_or_handle": "ministry_of_defense_ua", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Ukraine MFA (Telegram)", "kind": "telegram", "url_or_handle": "Ukraine_MFA", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "Ukraine Counter-Disinformation Centre (Telegram)", "kind": "telegram", "url_or_handle": "CenterCounteringDisinformation", "ao": "AO_NORTH", "reliability": "official"},
    {"name": "DeepState UA (Telegram)", "kind": "telegram", "url_or_handle": "DeepStateUA", "ao": "AO_NORTH", "reliability": "unverified"},
    {"name": "Motolko Help Belarus (Telegram)", "kind": "telegram", "url_or_handle": "motolkohelp", "ao": "AO_NORTH", "reliability": "unverified"},
    {"name": "Belsat (Telegram)", "kind": "telegram", "url_or_handle": "belsat", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "Charter 97 (Telegram)", "kind": "telegram", "url_or_handle": "charter97_org", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "UNITED24 Media (Telegram)", "kind": "telegram", "url_or_handle": "United24media", "ao": "AO_NORTH", "reliability": "established_media"},
    {"name": "WarTranslated (Telegram)", "kind": "telegram", "url_or_handle": "wartranslated", "ao": "AO_NORTH", "reliability": "regional_specialist"},
    {"name": "NOEL Reports (Telegram)", "kind": "telegram", "url_or_handle": "noel_reports", "ao": "AO_NORTH", "reliability": "unverified"},
    {"name": "Israel Defense Forces (Telegram)", "kind": "telegram", "url_or_handle": "idfofficial", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Aurora Intel (Telegram)", "kind": "telegram", "url_or_handle": "AuroraIntel", "ao": "AO_LEVANT", "reliability": "unverified"},
    {"name": "Intelsky (Telegram)", "kind": "telegram", "url_or_handle": "intelsky", "ao": "AO_LEVANT", "reliability": "unverified"},
    {"name": "Clash Report (Telegram)", "kind": "telegram", "url_or_handle": "ClashReport", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "Al Arabiya (Telegram)", "kind": "telegram", "url_or_handle": "alarabiya", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Al Hadath (Telegram)", "kind": "telegram", "url_or_handle": "AlHadath", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "OSINTtechnical (Telegram)", "kind": "telegram", "url_or_handle": "OSINTtechnical", "ao": "GLOBAL", "reliability": "unverified"},

    # Other public social feeds
    {"name": "Bellingcat (Bluesky)", "kind": "social",
     "url_or_handle": "https://bsky.app/profile/bellingcat.com/rss", "ao": "GLOBAL", "reliability": "regional_specialist"},
    {"name": "r/OSINT New Posts", "kind": "social",
     "url_or_handle": "https://www.reddit.com/r/OSINT/new/.rss", "ao": "GLOBAL", "reliability": "unverified"},

    # GitHub Atom — monitors the open-source tools and source packs feeding this ecosystem
    {"name": "GlobalPulse (GitHub)", "kind": "github",
     "url_or_handle": "https://github.com/ntamero/globalpulse/commits/main.atom", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "IRONSIGHT (GitHub)", "kind": "github",
     "url_or_handle": "https://github.com/NoblerWorks-HQ/IRONSIGHT/commits/main.atom", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "OSINT War Room (GitHub)", "kind": "github",
     "url_or_handle": "https://github.com/Hue-Jhan/OSINT-War-Room/commits/main.atom", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "Meridian Intel (GitHub)", "kind": "github",
     "url_or_handle": "https://github.com/sumsumai/meridian-intel/commits/main.atom", "ao": "GLOBAL", "reliability": "unverified"},
    {"name": "OSINTmonitor (GitHub)", "kind": "github",
     "url_or_handle": "https://github.com/marcko80/osintmonitor/commits/main.atom", "ao": "GLOBAL", "reliability": "unverified"},

    # Coverage expansion v6 — High North / Finland / Baltic states.
    # Direct feeds are used where reliable; official sites without feeds use
    # a populated site-restricted Google News RSS bridge.
    {"name": "Eye on the Arctic", "kind": "rss",
     "url_or_handle": "https://www.rcinet.ca/eye-on-the-arctic/feed/", "ao": "AO_HIGH_NORTH", "reliability": "established_media"},
    {"name": "Nunatsiaq News", "kind": "rss",
     "url_or_handle": "https://nunatsiaq.com/feed/", "ao": "AO_HIGH_NORTH", "reliability": "established_media"},
    {"name": "Iceland Review", "kind": "rss",
     "url_or_handle": "https://www.icelandreview.com/feed/", "ao": "AO_HIGH_NORTH", "reliability": "established_media"},
    {"name": "Estonian Defence Forces", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Amil.ee%2Fen+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Lithuanian Defence Ministry", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Akam.lt%2Fen+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Norwegian Armed Forces", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aforsvaret.no%2Fen+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Norwegian Government - High North", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aregjeringen.no%2Fen+%28Arctic+OR+High+North+OR+Barents%29+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Finnish Government Security", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Avaltioneuvosto.fi%2Fen+%28security+OR+defence+OR+border%29+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Government of Iceland Security", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Agovernment.is+%28security+OR+defence+OR+NATO%29+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Arctic Council News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aarctic-council.org%2Fnews+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Arctic Security Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Arctic+OR+Svalbard+OR+Barents%29+%28military+OR+security+OR+NATO+OR+Russia%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "unverified"},
    {"name": "Baltic Airspace Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Estonia+OR+Latvia+OR+Lithuania+OR+Finland%29+%28airspace+OR+drone+OR+incursion+OR+fighter%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "unverified"},
    {"name": "Nordic Infrastructure Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Finland+OR+Sweden+OR+Norway+OR+Baltic%29+%28cable+OR+pipeline+OR+sabotage+OR+jamming%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "unverified"},
    {"name": "Kola and Barents Military Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Murmansk+OR+Kola+OR+Barents%29+%28military+OR+submarine+OR+missile+OR+exercise%29+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_HIGH_NORTH", "reliability": "unverified"},

    # Coverage expansion v6 — Ukraine / eastern and central Europe.
    {"name": "Ukrinform English", "kind": "rss",
     "url_or_handle": "https://www.ukrinform.net/rss/block-lastnews", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Kyiv Post", "kind": "rss",
     "url_or_handle": "https://www.kyivpost.com/feed", "ao": "AO_EUROPE", "reliability": "established_media"},
    {"name": "Politico Europe", "kind": "rss",
     "url_or_handle": "https://www.politico.eu/feed/", "ao": "AO_EUROPE", "reliability": "established_media"},
    {"name": "European Council on Foreign Relations", "kind": "rss",
     "url_or_handle": "https://ecfr.eu/feed/", "ao": "AO_EUROPE", "reliability": "regional_specialist"},
    {"name": "Balkan Insight", "kind": "rss",
     "url_or_handle": "https://balkaninsight.com/feed/", "ao": "AO_EUROPE", "reliability": "regional_specialist"},
    {"name": "Ukraine Ministry of Defence English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Amod.gov.ua%2Fen%2Fnews+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "President of Ukraine English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Apresident.gov.ua%2Fen%2Fnews+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Government of Ukraine English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Akmu.gov.ua%2Fen%2Fnews+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Government of Moldova English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Agov.md%2Fen+%28security+OR+defence+OR+border+OR+Ukraine%29+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Croatian Defence Ministry English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Amorh.hr%2Fen+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Czech Defence Ministry English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Amo.gov.cz%2Fen+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "US European Command", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aeucom.mil+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Europol Newsroom", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aeuropol.europa.eu%2Fmedia-press%2Fnewsroom+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "ENISA Cybersecurity News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aenisa.europa.eu%2Fnews+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "EU Civil Protection - Ukraine", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Acivil-protection-humanitarian-aid.ec.europa.eu+Ukraine+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "EU Council - Ukraine", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aconsilium.europa.eu+Ukraine+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "NATO - Ukraine", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Anato.int+Ukraine+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Institute for Study of War - Ukraine", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aunderstandingwar.org+Ukraine+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "regional_specialist"},
    {"name": "ArmyInform English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aarmyinform.com.ua%2Fen+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Defence Express Ukraine English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aen.defence-ua.com+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "regional_specialist"},
    {"name": "Black Sea Security Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Black+Sea+OR+Romania+OR+Bulgaria+OR+Moldova%29+%28drone+OR+missile+OR+naval+OR+sabotage%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "unverified"},
    {"name": "Central Europe Hybrid Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Poland+OR+Germany+OR+Czechia+OR+Slovakia+OR+Austria%29+%28sabotage+OR+espionage+OR+drone+OR+cyberattack%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "unverified"},
    {"name": "Balkans Security Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Serbia+OR+Kosovo+OR+Bosnia+OR+Croatia+OR+Slovenia+OR+Albania%29+%28military+OR+security+OR+unrest%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "unverified"},
    {"name": "Ukraine Energy Infrastructure Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=Ukraine+%28power+grid+OR+energy+infrastructure+OR+substation+OR+nuclear+plant%29+%28strike+OR+attack+OR+damage%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "unverified"},
    {"name": "Ukraine Maritime Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Odesa+OR+Crimea+OR+Black+Sea+OR+Azov%29+%28drone+OR+missile+OR+vessel+OR+port%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_EUROPE", "reliability": "unverified"},
    {"name": "Security Service of Ukraine (Telegram)", "kind": "telegram", "url_or_handle": "SBUkr", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Ukraine State Border Guard (Telegram)", "kind": "telegram", "url_or_handle": "DPSUkr", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Ukraine Emergency Service (Telegram)", "kind": "telegram", "url_or_handle": "dsns_telegram", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Ukraine Navy (Telegram)", "kind": "telegram", "url_or_handle": "ukrainian_navy", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "President Zelenskyy (Telegram)", "kind": "telegram", "url_or_handle": "V_Zelenskiy_official", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Ukraine National Police (Telegram)", "kind": "telegram", "url_or_handle": "UA_National_Police", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Operational Armed Forces Ukraine (Telegram)", "kind": "telegram", "url_or_handle": "operativnoZSU", "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "SPRAVDI StratCom (Telegram)", "kind": "telegram", "url_or_handle": "spravdi", "ao": "AO_EUROPE", "reliability": "official"},

    # Coverage expansion v6 — Levant / Lebanon / Jordan focus.
    {"name": "Roya News English", "kind": "rss",
     "url_or_handle": "https://en.royanews.tv/rss", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Syria Direct", "kind": "rss",
     "url_or_handle": "https://syriadirect.org/feed/", "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Alma Research Center", "kind": "rss",
     "url_or_handle": "https://israel-alma.org/feed/", "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "UNSCOL Lebanon", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aunscol.unmissions.org%2Fen+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "OCHA occupied Palestinian territory", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aochaopt.org+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "UNRWA Updates", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aunrwa.org+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Lebanon National News Agency English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Anna-leb.gov.lb%2Fen+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Lebanese General Security English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Ageneral-security.gov.lb%2Fen+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Jordan Times via Google News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Ajordantimes.com+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Enab Baladi English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aenglish.enabbaladi.net+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "established_media"},
    {"name": "Syrian Observatory for Human Rights", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Asyriahr.com%2Fen+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "unverified"},
    {"name": "INSS Israel", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Ainss.org.il+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Washington Institute", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Awashingtoninstitute.org+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "FDD Middle East", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Afdd.org+%28Lebanon+OR+Jordan+OR+Syria+OR+Israel+OR+Iran%29+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "WAFA English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aenglish.wafa.ps+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "IDF English News", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aidf.il%2Fen+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "OCHA Syria", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aunocha.org+Syria+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "UN Security Council - Lebanon", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Apress.un.org+Lebanon+when%3A30d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Critical Threats Project - Iran", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Acriticalthreats.org+Iran+when%3A14d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Lebanon Border Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Lebanon+OR+Beirut+OR+Litani%29+%28strike+OR+shelling+OR+border+OR+Hezbollah%29+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "unverified"},
    {"name": "Jordan Border Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=Jordan+%28border+OR+smuggling+OR+drone+OR+security+OR+military%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "unverified"},
    {"name": "Syria Security Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=Syria+%28strike+OR+bombing+OR+clash+OR+security+operation%29+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "unverified"},
    {"name": "Red Sea Maritime Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Red+Sea+OR+Bab+el-Mandeb+OR+Gulf+of+Aqaba%29+%28attack+OR+drone+OR+missile+OR+vessel%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "unverified"},
    {"name": "Levant Airspace Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Lebanon+OR+Jordan+OR+Syria+OR+Israel%29+%28airspace+OR+drone+OR+missile+OR+interception%29+when%3A3d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_LEVANT", "reliability": "unverified"},

    # Coverage expansion v7 — The Balkans
    {"name": "Serbia Ministry of Defence English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Amod.gov.rs%2Feng+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Bosnia and Herzegovina Defence English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Amod.gov.ba+langTag%3Den-US+when%3A180d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Slovenia Ministry of Defence English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Agov.si%2Fen%2Fstate-authorities%2Fministries%2Fministry-of-defence+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "North Macedonia Defence English", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Amod.gov.mk%2Fen-GB+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "EUFOR Althea", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Aeuforbih.org+%28news+OR+statement%29+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "NATO KFOR", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=site%3Ajfcnaples.nato.int%2Fkfor+when%3A60d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Western Balkans Security Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Serbia+OR+Kosovo+OR+Bosnia+OR+Croatia+OR+Slovenia+OR+Albania+OR+Montenegro+OR+Macedonia%29+%28military+OR+security+OR+unrest%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "Serbia Kosovo Security Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Serbia+OR+Kosovo%29+%28KFOR+OR+border+OR+military+OR+security+OR+unrest%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "Bosnia EUFOR Security Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Bosnia+OR+Republika+Srpska%29+%28EUFOR+OR+security+OR+secession+OR+military%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "Balkan Airspace and Infrastructure Watch", "kind": "rss",
     "url_or_handle": "https://news.google.com/rss/search?q=%28Balkans+OR+Adriatic+OR+Serbia+OR+Croatia+OR+Bulgaria+OR+Greece%29+%28airspace+OR+drone+OR+infrastructure+OR+sabotage%29+when%3A7d&hl=en-GB&gl=GB&ceid=GB%3Aen", "ao": "AO_BALKANS", "reliability": "unverified"},
])

# ---------------------------------------------------------------------------
# Coverage expansion v8 — verified institutional and regional discovery pack.
# The Balkans receives the largest uplift because the previous catalogue was
# disproportionately small. Site-restricted feeds retain the publisher's name
# and reliability while avoiding fragile scraping of sites without RSS.
# ---------------------------------------------------------------------------
SOURCES.extend([
    # AO BALKANS — national authorities and international security missions
    {"name": "Albania Ministry of Defence English", "kind": "rss", "url_or_handle": _google_news("site:mod.gov.al/eng defence OR security when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Kosovo Online English", "kind": "rss", "url_or_handle": _google_news("site:kosovo-online.com/en Kosovo when:14d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Albanian Daily News", "kind": "rss", "url_or_handle": _google_news("site:albaniandailynews.com security OR politics when:14d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Kosovo Police English", "kind": "rss", "url_or_handle": _google_news("site:kosovopolice.com/en security OR police OR border when:30d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "MIA North Macedonia English", "kind": "rss", "url_or_handle": _google_news("site:mia.mk/en Macedonia when:14d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Greece Ministry of National Defence English", "kind": "rss", "url_or_handle": _google_news("site:mod.mil.gr/en defence OR armed forces when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Croatia Week", "kind": "rss", "url_or_handle": _google_news("site:croatiaweek.com security OR defence OR politics when:30d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Serbia Interior Ministry English", "kind": "rss", "url_or_handle": _google_news("site:mup.gov.rs/wps/portal/en police OR security when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "EULEX Kosovo", "kind": "rss", "url_or_handle": _google_news("site:eulex-kosovo.eu news when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Office of the High Representative Bosnia", "kind": "rss", "url_or_handle": _google_news("site:ohr.int Bosnia statement OR communique when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "NATO Headquarters Sarajevo", "kind": "rss", "url_or_handle": _google_news("site:jfcnaples.nato.int/hqsarajevo when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "OSCE Mission to Bosnia and Herzegovina", "kind": "rss", "url_or_handle": _google_news("site:osce.org/mission-to-bosnia-and-herzegovina security OR stability when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Balkan Green Energy and Infrastructure", "kind": "rss", "url_or_handle": _google_news("site:balkangreenenergynews.com infrastructure OR energy security when:30d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Regional Cooperation Council", "kind": "rss", "url_or_handle": _google_news("site:rcc.int Western Balkans security OR radicalisation OR organised crime when:90d"), "ao": "AO_BALKANS", "reliability": "official"},

    # AO BALKANS — established regional media
    {"name": "European Western Balkans", "kind": "rss", "url_or_handle": _google_news("site:europeanwesternbalkans.com when:14d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "N1 Balkans English", "kind": "rss", "url_or_handle": _google_news("site:n1info.rs/english Serbia OR Kosovo OR Bosnia when:14d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Sarajevo Times", "kind": "rss", "url_or_handle": "https://sarajevotimes.com/feed/", "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Exit News Albania", "kind": "rss", "url_or_handle": _google_news("site:exit.al/en Albania when:14d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "eKathimerini Greece", "kind": "rss", "url_or_handle": _google_news("site:ekathimerini.com Greece when:14d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Bulgarian News Agency English", "kind": "rss", "url_or_handle": _google_news("site:bta.bg/en Bulgaria when:14d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "RFE/RL Western Balkans", "kind": "rss", "url_or_handle": _google_news("site:rferl.org Kosovo OR Serbia OR Bosnia OR Montenegro OR Albania when:14d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "DW Western Balkans", "kind": "rss", "url_or_handle": _google_news("site:dw.com Balkans OR Kosovo OR Serbia OR Bosnia when:14d"), "ao": "AO_BALKANS", "reliability": "established_media"},

    # AO BALKANS — security-policy and regional specialist analysis
    {"name": "Belgrade Centre for Security Policy", "kind": "rss", "url_or_handle": _google_news("site:bezbednost.org/en security when:90d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Kosovar Centre for Security Studies", "kind": "rss", "url_or_handle": _google_news("site:qkss.org/en security when:180d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Balkans Policy Research Group", "kind": "rss", "url_or_handle": _google_news("site:balkansgroup.org/en Kosovo OR Serbia OR Balkans when:180d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Balkans in Europe Policy Advisory Group", "kind": "rss", "url_or_handle": _google_news("site:biepag.eu Balkans when:180d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Greek Reporter Security", "kind": "rss", "url_or_handle": _google_news("site:greekreporter.com Greece security OR defence when:14d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Center for the Study of Democracy Bulgaria", "kind": "rss", "url_or_handle": _google_news("site:csd.eu security Bulgaria OR Balkans when:180d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "ELIAMEP Greece", "kind": "rss", "url_or_handle": _google_news("site:eliamep.gr/en security OR defence OR Balkans when:90d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Institute Alternative Montenegro", "kind": "rss", "url_or_handle": _google_news("site:institut-alternativa.org/en security OR governance Montenegro when:180d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},

    # AO BALKANS — focused warning and indicator feeds
    {"name": "Balkan Protest and Public Order Watch", "kind": "rss", "url_or_handle": _google_news("(Serbia OR Greece OR Bulgaria OR Albania OR Montenegro OR Macedonia) (protest OR riot OR blockade OR police) when:3d"), "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "Balkan Organised Crime and Arms Watch", "kind": "rss", "url_or_handle": _google_news("(Balkans OR Serbia OR Kosovo OR Bosnia OR Albania OR Montenegro) (organised crime OR weapons trafficking OR smuggling OR police raid) when:7d"), "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "Balkan Foreign Influence Watch", "kind": "rss", "url_or_handle": _google_news("(Western Balkans OR Serbia OR Bosnia OR Montenegro OR North Macedonia) (Russian influence OR Chinese influence OR disinformation OR hybrid threat) when:14d"), "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "North Kosovo Warning Watch", "kind": "rss", "url_or_handle": _google_news("(North Kosovo OR Mitrovica OR Zvecan OR Banjska) (KFOR OR police OR clash OR border OR security) when:7d"), "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "Bosnia Constitutional Stability Watch", "kind": "rss", "url_or_handle": _google_news("(Bosnia OR Republika Srpska OR Dodik) (secession OR constitutional crisis OR EUFOR OR security) when:7d"), "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "Aegean Security Watch", "kind": "rss", "url_or_handle": _google_news("(Greece OR Aegean) (airspace OR interception OR coast guard OR drone OR military) when:7d"), "ao": "AO_BALKANS", "reliability": "unverified"},
    {"name": "Southern Balkans Border Watch", "kind": "rss", "url_or_handle": _google_news("(Albania OR Montenegro OR North Macedonia OR Bulgaria) (border OR smuggling OR security operation OR weapons) when:7d"), "ao": "AO_BALKANS", "reliability": "unverified"},

    # AO HIGH NORTH — intelligence, border and resilience authorities
    {"name": "Swedish Defence Research Agency", "kind": "rss", "url_or_handle": _google_news("site:foi.se/en security OR defence when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Finnish Border Guard English", "kind": "rss", "url_or_handle": _google_news("site:raja.fi/en border OR security when:60d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Swedish Security Service English", "kind": "rss", "url_or_handle": _google_news("site:sakerhetspolisen.se/ovriga-sidor/other-languages/english security when:120d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Norwegian Institute of International Affairs", "kind": "rss", "url_or_handle": _google_news("site:nupi.no/en Arctic OR Russia OR security when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "regional_specialist"},
    {"name": "Latvia Ministry of Defence English", "kind": "rss", "url_or_handle": _google_news("site:mod.gov.lv/en defence OR security when:60d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Lithuanian State Security Department English", "kind": "rss", "url_or_handle": _google_news("site:vsd.lt/en security OR threat when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Finnish Institute of International Affairs", "kind": "rss", "url_or_handle": _google_news("site:fiia.fi/en Arctic OR Baltic OR security when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "regional_specialist"},
    {"name": "Danish Institute for International Studies", "kind": "rss", "url_or_handle": _google_news("site:diis.dk/en Arctic OR Baltic OR security when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "regional_specialist"},

    # AO UKRAINE AND EASTERN EUROPE — eastern flank authorities
    {"name": "Poland Ministry of National Defence English", "kind": "rss", "url_or_handle": _google_news("site:gov.pl/web/national-defence defence OR security when:60d"), "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Romania Ministry of National Defence English", "kind": "rss", "url_or_handle": _google_news("site:english.mapn.ro defence OR military when:60d"), "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Romanian Border Police English", "kind": "rss", "url_or_handle": _google_news("site:politiadefrontiera.ro/en border OR Ukraine OR Black Sea when:60d"), "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Moldova Border Police English", "kind": "rss", "url_or_handle": _google_news("site:border.gov.md/en border OR security when:60d"), "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Moldova Intelligence and Security Service", "kind": "rss", "url_or_handle": _google_news("site:sis.md/en security OR intelligence when:180d"), "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Bundeswehr English", "kind": "rss", "url_or_handle": _google_news("site:bundeswehr.de/en Ukraine OR eastern flank OR NATO when:60d"), "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "NATO Eastern Flank Watch", "kind": "rss", "url_or_handle": _google_news("site:nato.int (eastern flank OR Poland OR Romania OR Black Sea) when:30d"), "ao": "AO_EUROPE", "reliability": "official"},
    {"name": "Ukraine Critical Infrastructure Official Watch", "kind": "rss", "url_or_handle": _google_news("site:gov.ua/en Ukraine (energy OR infrastructure OR emergency) when:14d"), "ao": "AO_EUROPE", "reliability": "official"},

    # AO LEVANT — security services, UN monitoring and regional analysis
    {"name": "Lebanese Center for Policy Studies", "kind": "rss", "url_or_handle": _google_news("site:lcps-lebanon.org security OR governance when:180d"), "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Middle East Council on Global Affairs", "kind": "rss", "url_or_handle": _google_news("site:mecouncil.org Lebanon OR Jordan OR Syria when:90d"), "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "UNDOF Golan Heights", "kind": "rss", "url_or_handle": _google_news("site:undof.unmissions.org Golan OR ceasefire when:90d"), "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "UNTSO Middle East", "kind": "rss", "url_or_handle": _google_news("site:untso.unmissions.org ceasefire OR observers when:120d"), "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "OCHA Lebanon", "kind": "rss", "url_or_handle": _google_news("site:unocha.org Lebanon humanitarian OR displacement when:30d"), "ao": "AO_LEVANT", "reliability": "official"},
    {"name": "Malcolm H. Kerr Carnegie Middle East Center", "kind": "rss", "url_or_handle": _google_news("site:carnegieendowment.org/middle-east Lebanon OR Syria OR Jordan when:90d"), "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "Arab Center Washington DC", "kind": "rss", "url_or_handle": _google_news("site:arabcenterdc.org Lebanon OR Jordan OR Syria OR Israel when:90d"), "ao": "AO_LEVANT", "reliability": "regional_specialist"},
    {"name": "ICRC Lebanon and Syria", "kind": "rss", "url_or_handle": _google_news("site:icrc.org Lebanon OR Syria when:30d"), "ao": "AO_LEVANT", "reliability": "official"},
])

# Coverage expansion v9 — High North and Balkans depth pack. Every query below
# was live-tested and required to return populated results before inclusion.
SOURCES.extend([
    # AO HIGH NORTH — authorities, maritime security and resilience
    {"name": "Danish Armed Forces English", "kind": "rss", "url_or_handle": _google_news("site:forsvaret.dk/en Arctic OR Baltic OR defence when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Danish Ministry of Defence English", "kind": "rss", "url_or_handle": _google_news("site:fmn.dk/en Arctic OR defence OR security when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Government of the Faroe Islands English", "kind": "rss", "url_or_handle": _google_news("site:government.fo/en/news security OR Arctic OR defence when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Estonian Internal Security Service English", "kind": "rss", "url_or_handle": _google_news("site:kapo.ee/en security OR threat when:365d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Latvian State Security Service English", "kind": "rss", "url_or_handle": _google_news("site:vdd.gov.lv/en news security OR threat when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Lithuanian Armed Forces English", "kind": "rss", "url_or_handle": _google_news("site:kariuomene.lt/en defence OR exercise OR Baltic when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Norwegian Coastal Administration English", "kind": "rss", "url_or_handle": _google_news("site:kystverket.no/en news Arctic OR security OR navigation when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Norwegian Defence Research Establishment", "kind": "rss", "url_or_handle": _google_news("site:ffi.no/en Arctic OR High North OR Russia when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "Swedish Coast Guard English", "kind": "rss", "url_or_handle": _google_news("site:kustbevakningen.se/en Baltic OR security OR coast guard when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "NATO Joint Force Command Norfolk", "kind": "rss", "url_or_handle": _google_news("site:jfcnorfolk.nato.int High North OR Arctic OR Baltic when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},
    {"name": "NATO Maritime Command Baltic", "kind": "rss", "url_or_handle": _google_news("site:mc.nato.int Baltic OR Arctic when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "official"},

    # AO HIGH NORTH — specialist analysis and defence media
    {"name": "Baltic Defence College", "kind": "rss", "url_or_handle": _google_news("site:baltdefcol.org security OR defence when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "regional_specialist"},
    {"name": "International Centre for Defence and Security Estonia", "kind": "rss", "url_or_handle": _google_news("site:icds.ee/en Baltic OR Nordic OR Russia when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "regional_specialist"},
    {"name": "Latvian Institute of International Affairs", "kind": "rss", "url_or_handle": _google_news("site:liia.lv/en Baltic OR security OR Russia when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "regional_specialist"},
    {"name": "Swedish Institute of International Affairs", "kind": "rss", "url_or_handle": _google_news("site:ui.se/english Baltic OR Arctic OR security when:180d"), "ao": "AO_HIGH_NORTH", "reliability": "regional_specialist"},
    {"name": "The Arctic Institute Security", "kind": "rss", "url_or_handle": _google_news("site:thearcticinstitute.org security OR defence when:90d"), "ao": "AO_HIGH_NORTH", "reliability": "regional_specialist"},
    {"name": "Arctic Today Security", "kind": "rss", "url_or_handle": _google_news("site:arctictoday.com security OR military OR Russia when:30d"), "ao": "AO_HIGH_NORTH", "reliability": "established_media"},
    {"name": "Naval News High North and Baltic", "kind": "rss", "url_or_handle": _google_news("site:navalnews.com Arctic OR Baltic OR Norway OR Sweden OR Finland when:30d"), "ao": "AO_HIGH_NORTH", "reliability": "established_media"},
    {"name": "USNI News Arctic and Baltic", "kind": "rss", "url_or_handle": _google_news("site:news.usni.org Arctic OR Baltic OR High North when:60d"), "ao": "AO_HIGH_NORTH", "reliability": "established_media"},
    {"name": "Breaking Defense Nordic and Arctic", "kind": "rss", "url_or_handle": _google_news("site:breakingdefense.com Arctic OR Nordic OR Baltic when:60d"), "ao": "AO_HIGH_NORTH", "reliability": "established_media"},
    {"name": "Defense News Nordic and Baltic", "kind": "rss", "url_or_handle": _google_news("site:defensenews.com Nordic OR Baltic OR Arctic when:30d"), "ao": "AO_HIGH_NORTH", "reliability": "established_media"},
    {"name": "Nordic Cyber Security Watch", "kind": "rss", "url_or_handle": _google_news("(Finland OR Sweden OR Norway OR Estonia OR Latvia OR Lithuania) (cyberattack OR ransomware OR critical infrastructure) when:7d"), "ao": "AO_HIGH_NORTH", "reliability": "unverified"},

    # AO BALKANS — police, border, defence and international missions
    {"name": "Montenegro Ministry of Defence English", "kind": "rss", "url_or_handle": _google_news("site:gov.me defence Montenegro when:365d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Montenegro Police and Interior English", "kind": "rss", "url_or_handle": _google_news("site:gov.me police Montenegro security when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Bosnia State Investigation and Protection Agency", "kind": "rss", "url_or_handle": _google_news("site:sipa.gov.ba/en security OR arrest OR operation when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Bosnia Border Police English", "kind": "rss", "url_or_handle": _google_news("site:granpol.gov.ba border OR security when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "North Macedonia Interior Ministry English", "kind": "rss", "url_or_handle": _google_news("site:mvr.gov.mk/en police OR security when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Bulgaria Interior Ministry English", "kind": "rss", "url_or_handle": _google_news("site:mvr.bg/en police OR security when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Slovenian Police English", "kind": "rss", "url_or_handle": _google_news("site:policija.si/eng news security OR police when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "OSCE Mission in Kosovo", "kind": "rss", "url_or_handle": _google_news("site:osce.org Kosovo mission security when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "OSCE Mission to Serbia", "kind": "rss", "url_or_handle": _google_news("site:osce.org/mission-to-serbia security OR police when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "OSCE Mission to Skopje", "kind": "rss", "url_or_handle": _google_news("site:osce.org Skopje mission security when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "OSCE Mission to Montenegro", "kind": "rss", "url_or_handle": _google_news("site:osce.org Montenegro mission security when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "OSCE Presence in Albania", "kind": "rss", "url_or_handle": _google_news("site:osce.org Albania presence security when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Frontex Western Balkans", "kind": "rss", "url_or_handle": _google_news("site:frontex.europa.eu Western Balkans OR Serbia OR Albania OR Bosnia when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "Europol Western Balkans", "kind": "rss", "url_or_handle": _google_news("site:europol.europa.eu Western Balkans OR Serbia OR Albania OR Bosnia when:90d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "UNODC South Eastern Europe", "kind": "rss", "url_or_handle": _google_news("site:unodc.org/southeasterneurope Balkans OR Serbia OR Bosnia OR Albania when:180d"), "ao": "AO_BALKANS", "reliability": "official"},
    {"name": "WeBalkans EU", "kind": "rss", "url_or_handle": _google_news("site:webalkans.eu/en news security OR defence OR resilience when:90d"), "ao": "AO_BALKANS", "reliability": "official"},

    # AO BALKANS — local English media and specialist security analysis
    {"name": "SEESAC Arms Control Balkans", "kind": "rss", "url_or_handle": _google_news("site:seesac.org security OR arms OR Balkans when:180d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "RACVIAC Centre for Security Cooperation", "kind": "rss", "url_or_handle": _google_news("site:racviac.org security OR Balkans when:180d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "DCAF South East Europe", "kind": "rss", "url_or_handle": _google_news("site:dcaf.ch South East Europe OR Balkans OR Kosovo when:180d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Global Initiative Western Balkans Observatory", "kind": "rss", "url_or_handle": _google_news("site:globalinitiative.net Western Balkans OR Serbia OR Kosovo OR Bosnia when:90d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "IDSCS North Macedonia", "kind": "rss", "url_or_handle": _google_news("site:idscs.org.mk/en security OR Macedonia when:365d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Analytica North Macedonia", "kind": "rss", "url_or_handle": _google_news("site:analyticamk.org security OR Macedonia when:365d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Kosovo 2.0 English", "kind": "rss", "url_or_handle": _google_news("site:kosovotwopointzero.com/en Kosovo when:30d"), "ao": "AO_BALKANS", "reliability": "regional_specialist"},
    {"name": "Prishtina Insight", "kind": "rss", "url_or_handle": _google_news("site:prishtinainsight.com Kosovo when:30d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Tirana Times", "kind": "rss", "url_or_handle": _google_news("site:tiranatimes.com Albania security OR politics when:60d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Total Croatia News", "kind": "rss", "url_or_handle": _google_news("site:total-croatia-news.com Croatia security OR defence OR politics when:30d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Slovenia Times English", "kind": "rss", "url_or_handle": _google_news("site:sloveniatimes.com security OR defence OR politics when:60d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "STA Slovenian Press Agency English", "kind": "rss", "url_or_handle": _google_news("site:english.sta.si Slovenia security OR defence when:30d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Tanjug English", "kind": "rss", "url_or_handle": _google_news("site:tanjug.rs/english Serbia security OR Kosovo when:30d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "SeeNews Western Balkans", "kind": "rss", "url_or_handle": _google_news("site:seenews.com Western Balkans OR Serbia OR Bosnia OR Albania when:30d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "bne IntelliNews Western Balkans", "kind": "rss", "url_or_handle": _google_news("site:intellinews.com Western Balkans OR Serbia OR Kosovo OR Bosnia when:30d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Euractiv Western Balkans", "kind": "rss", "url_or_handle": _google_news("site:euractiv.com Western Balkans OR Serbia OR Kosovo when:30d"), "ao": "AO_BALKANS", "reliability": "established_media"},
    {"name": "Balkan Defence Procurement Watch", "kind": "rss", "url_or_handle": _google_news("(Serbia OR Croatia OR Albania OR Kosovo OR Bulgaria OR Greece) (weapons purchase OR defence procurement OR military acquisition) when:14d"), "ao": "AO_BALKANS", "reliability": "unverified"},
])

# Split the original combined northern-Europe collection pack into the two
# distinct AOs. Keeping this routing in one explicit table prevents individual
# source declarations added over several versions from silently retaining the
# retired AO_NORTH label.
HIGH_NORTH_SOURCE_NAMES = {
    "The Baltic Times",
    "Latvian Public Media (LSM English)",
    "Radio Sweden English",
    "Norway's News in English (newsinenglish.no)",
    "OSINT: Baltics watcher (X)",
    "Estonian Public Broadcasting (ERR English)",
    "Yle News (Finland)",
    "SVT Nyheter (Sweden)",
    "Traficom Finland (English)",
    "LRT English via Google News",
    "High North News via Google News",
    "Barents Observer via Google News",
    "NATO News via Google News",
    "Hybrid CoE via Google News",
    "NATO StratCom COE via Google News",
    "Finnish Defence Forces via Google News",
    "Swedish Armed Forces via Google News",
    "Baltic Infrastructure & GNSS Watch",
}

GLOBAL_DEFENCE_SOURCE_NAMES = {
    "Defense One",
    "RealClearDefense",
    "Defence Blog",
    "UK Defence Journal",
    "Breaking Defense",
    "War on the Rocks",
    "Task & Purpose",
    "Military Watch Magazine",
}

for source in SOURCES:
    if source["ao"] != "AO_NORTH":
        continue
    if source["name"] in HIGH_NORTH_SOURCE_NAMES:
        source["ao"] = "AO_HIGH_NORTH"
    elif source["name"] in GLOBAL_DEFENCE_SOURCE_NAMES:
        source["ao"] = "GLOBAL"
    else:
        source["ao"] = "AO_EUROPE"

BALKANS_SOURCE_NAMES = {
    "Balkan Insight",
    "Balkans Security Watch",
    "Croatian Defence Ministry English",
}

for source in SOURCES:
    if source["name"] in BALKANS_SOURCE_NAMES:
        source["ao"] = "AO_BALKANS"

# URLs retired from SOURCES (confirmed dead / moved in prior versions).
# Kept here so seed_sources() can auto-clean them from the database on startup.
RETIRED_SOURCE_URLS = [
    "https://www.understandingwar.org/rss.xml",
    "https://thebarentsobserver.com/en/rss.xml",
    "https://www.highnorthnews.com/en/rss.xml",
    "https://www.lrt.lt/en/rss",
    "https://feeds.yle.fi/uutiset/v1/majorNews/YLE_UUTISET.rss",
    "https://www.nato.int/cps/en/natohq/news.rss",
    "https://www.naharnet.com/stories.rss",
    "https://today.lorientlejour.com/rss",
    "https://www.jordantimes.com/rss.xml",
    "https://en.royanews.tv/rss",
    "https://www.reutersagency.com/feed/?best-topics=middle-east",
    "https://unifil.unmissions.org/rss.xml",
    "https://jamestown.org/feed/",
    "https://www.highnorthnews.com/en/feed",
    "https://www.arctictoday.com/feed/",
    "https://www.thearcticinstitute.org/feed/",
    "https://www.militarytimes.com/arc/outboundfeeds/rss/",
    "https://www.navalnews.com/feed/",
    "https://feeds.stripes.com/starsandstripes/news",
    "https://www.timesofisrael.com/feed/",
    "https://www.haaretz.com/srv/israel-news",
    "https://apnews.com/rss",
    "https://www.centcom.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=1&max=10",
    "https://www.euronews.com/rss",
    "https://www.iiss.org/publications/rss",
    "https://feeds.stripes.com/news/us/military",   # fixed path
    "https://kyivindependent.com/rss/",             # fixed path
    "https://apnews.com/hub/world-news/feed",        # fixed path
    "https://en.highnorthnews.com/feed",             # fixed domain
    "https://www.militarytimes.com/m/rss/",         # fixed path
    "https://www.haaretz.com/cmlink/1.628749",       # fixed path
    "https://www.stripes.com/rss",         # fixed URL
    "https://www.militarytimes.com/rss/all/",  # fixed URL
    "https://www.haaretz.com/srv/haaretz-latest",  # fixed URL
    "https://kyivindependent.com/feed/",   # fixed URL
    "https://en.highnorthnews.com/rss",    # fixed URL
    "https://feeds.apnews.com/rss/apf-topnews",  # DNS fails
    "https://www.centcom.mil/RSS/",         # 403, fixed path
    "https://www.iiss.org/rss/",            # 403, fixed path
    "https://www.danielpipes.org/rss.xml",
    "https://merip.org/feed/",
    "https://www.jta.org/feed",
]
