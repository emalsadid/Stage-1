"""
Path2Ascension Lead Qualifier — Configuration
All halal filter rules and ICP scoring criteria live here.
Edit this file to tune filters without touching core logic.
"""

# ---------------------------------------------------------------------------
# HALAL FILTER — LAYER 1: Industry tag blocklist
# Matches against the "Industry" column in Apollo / Instantly exports.
# Case-insensitive, substring match.
# ---------------------------------------------------------------------------
NON_HALAL_INDUSTRIES = [
    # Gambling
    "gambling", "casino", "lottery", "betting", "wagering", "sportsbook",
    # Alcohol
    "alcohol", "brewery", "distillery", "winery", "wine", "beer", "spirits",
    "liquor", "beverage alcohol",
    # Cannabis
    "cannabis", "marijuana", "hemp", "recreational drug",
    # Weapons / Arms (block manufacturers, not cyber/defense software)
    "firearms", "ammunition", "arms dealer", "weapons manufacturer", "gun",
    # Interest-based Finance
    "payday loan", "consumer lending", "mortgage lending", "credit card",
    "predatory finance", "pawnshop",
    # Insurance
    "insurance",
    # Adult Entertainment
    "adult entertainment", "pornography", "escort", "strip club",
    # Music industry (labels / distribution)
    "record label", "music label", "music publishing", "music distribution",
    # General Entertainment (film studios, streaming, TV networks)
    "film studio", "movie studio", "motion picture", "television network",
    "streaming entertainment",
    # Tobacco
    "tobacco", "cigarette", "vaping", "e-cigarette",
]

# ---------------------------------------------------------------------------
# HALAL FILTER — LAYER 2: Keyword blocklist for company descriptions & websites
# Matched against: Apollo "SEO Description" field + scraped homepage text.
# Case-insensitive, whole-word / phrase match.
# ---------------------------------------------------------------------------
NON_HALAL_KEYWORDS = [
    # Gambling
    "gambling", "casino", "poker", "slot machine", "slots", "lottery",
    "sports betting", "wagering", "sportsbook", "bet on",
    # Alcohol
    "alcoholic beverage", "craft beer", "craft brewery", "winery",
    "distillery", "spirits brand", "wine brand", "liquor store",
    # Cannabis
    "cannabis", "marijuana", "dispensary", "weed delivery", "hemp extract",
    "recreational cannabis", "medical marijuana",
    # Weapons
    "firearms dealer", "gun shop", "ammunition supplier", "arms manufacturer",
    # Interest-based Finance
    "payday loan", "high-interest loan", "predatory lending",
    "usury", "interest-bearing loan", "subprime",
    # Insurance
    "insurance carrier", "insurance underwriting", "life insurance",
    "auto insurance", "health insurance provider", "insurance broker",
    # Adult
    "adult content", "adult entertainment", "pornography", "xxx",
    "escort service", "strip club",
    # Music
    "record label", "music label", "music publishing",
    "signed artist", "music distribution platform",
    # Entertainment
    "movie studio", "film production company", "tv network",
    "streaming service", "entertainment company",
    # Tobacco
    "tobacco company", "cigarette brand", "vaping products",
]

# ---------------------------------------------------------------------------
# ICP SCORING CRITERIA
# Each matched criterion adds `weight` points to the lead's score.
# Leads scoring >= ICP_PASS_THRESHOLD pass to the output list.
# ---------------------------------------------------------------------------
ICP_PASS_THRESHOLD = 4  # minimum score to be considered qualified

ICP_CRITERIA = [
    {
        "name": "target_industry",
        "field": "industry",
        "matches": [
            "telecom", "telecommunications",
            "healthcare", "health tech", "medtech", "digital health",
            "cloud", "cloud infrastructure", "cloud computing",
            "cybersecurity", "information security", "infosec",
            "logistics", "supply chain", "freight tech",
            "saas", "software as a service",
            "technology", "information technology",
            "enterprise software",
        ],
        "weight": 3,
        "match_type": "substring_any",
    },
    {
        "name": "employee_count",
        "field": "employees",
        "range": (11, 200),
        "weight": 2,
        "match_type": "range",
    },
    {
        "name": "us_location",
        "field": "country",
        "matches": ["united states", "usa", "us"],
        "weight": 2,
        "match_type": "substring_any",
    },
    {
        "name": "decision_maker_title",
        "field": "title",
        "matches": [
            "vp of sales", "vp sales", "vice president of sales",
            "vp of marketing", "vp marketing", "vice president of marketing",
            "ceo", "chief executive", "founder", "co-founder",
            "head of growth", "head of demand gen", "head of sales",
            "director of sales", "director of marketing",
            "director of demand generation",
            "chief revenue officer", "cro",
            "chief marketing officer", "cmo",
            "growth marketing", "outbound sales", "bdr manager", "sdr manager",
        ],
        "weight": 2,
        "match_type": "substring_any",
    },
    {
        "name": "revenue_range",
        "field": "annual_revenue",
        "range": (1_000_000, 50_000_000),
        "weight": 1,
        "match_type": "range",
    },
    {
        "name": "recent_funding",
        "field": "latest_funding",
        "matches": ["series a", "series b", "seed", "pre-seed", "angel"],
        "weight": 1,
        "match_type": "substring_any",
    },
]

# ---------------------------------------------------------------------------
# APOLLO CSV FIELD MAPPING
# Maps Apollo's export column headers to internal field names used above.
# Update right-hand values if your export uses different column names.
# ---------------------------------------------------------------------------
APOLLO_FIELD_MAP = {
    "First Name":               "first_name",
    "Last Name":                "last_name",
    "Title":                    "title",
    "Company":                  "company",
    "Company Name for Emails":  "company_email_name",
    "Email":                    "email",
    "Email Status":             "email_status",
    "Industry":                 "industry",
    "# Employees":              "employees",
    "Website":                  "website",
    "LinkedIn Url":             "linkedin_url",
    "Company Linkedin Url":     "company_linkedin_url",
    "City":                     "city",
    "State":                    "state",
    "Country":                  "country",
    "SEO Description":          "seo_description",
    "Annual Revenue":           "annual_revenue",
    "Total Funding":            "total_funding",
    "Latest Funding":           "latest_funding",
    "Latest Funding Amount":    "latest_funding_amount",
    "Last Raised At":           "last_raised_at",
    "Technologies":             "technologies",
    "Keywords":                 "keywords",
    "Phone":                    "phone",
}

# Fields from other sources that map to the same internal names
INSTANTLY_FIELD_MAP = {
    "First Name":   "first_name",
    "Last Name":    "last_name",
    "Email":        "email",
    "Company Name": "company",
    "Website":      "website",
    "Industry":     "industry",
}

WELLFOUND_FIELD_MAP = {
    "Name":         "first_name",   # Wellfound usually has full name — split on load
    "Company":      "company",
    "Role":         "title",
    "Email":        "email",
    "Website":      "website",
    "Market":       "industry",     # Wellfound calls it "Market"
    "Team Size":    "employees",
    "Location":     "country",
}

LINKEDIN_FIELD_MAP = {
    "First Name":   "first_name",
    "Last Name":    "last_name",
    "Position":     "title",
    "Company":      "company",
    "Email Address": "email",
    "URL":          "linkedin_url",
    "Industry":     "industry",
    "Company Size": "employees",
    "Location":     "country",
}

# Ordered list of field maps to try when auto-detecting source
SOURCE_FIELD_MAPS = {
    "apollo":     APOLLO_FIELD_MAP,
    "instantly":  INSTANTLY_FIELD_MAP,
    "wellfound":  WELLFOUND_FIELD_MAP,
    "linkedin":   LINKEDIN_FIELD_MAP,
}

# ---------------------------------------------------------------------------
# WEBSITE SCRAPING CONFIG
# ---------------------------------------------------------------------------
SCRAPE_TIMEOUT_SECONDS = 6
SCRAPE_MAX_CHARS = 5000       # Only read first N chars of homepage HTML
USER_AGENT = (
    "Mozilla/5.0 (compatible; Path2AscensionBot/1.0; lead qualification)"
)
