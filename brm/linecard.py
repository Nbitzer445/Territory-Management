"""The Big Rivers Marketing line card for Nebraska & Iowa.

Transcribed from BigRiversLineCardNEIA.pdf. This is the authoritative list of
what Nathen actually represents -- the sales export contains some legacy and
house items that aren't lines on the card, and the card contains lines that
haven't shown sales yet. News and partner views key off this file.

`context` terms disambiguate generic brand names in news searches: without
them, "Salo", "Bootz", "Harris" and "Stingray" return mostly noise.

`db_aliases` map a card entry onto however the brand is spelled in the CRM
exports (e.g. "BRM Sales / Little Giant", "MAAX/AKER (American Bath Group)").
"""

# Corporate partners and the brands under them, page 1 of the card.
# BRM Sales stock product is page 2 (parent None).
LINE_CARD = [
    # --- A.O. Smith Corporation ---
    {"brand": "American Water Heaters", "parent": "A.O. Smith", "product": "Commercial, residential & tankless water heaters",
     "context": "water heater", "territory": "IA, NE, KS, MO, S IL",
     "db_aliases": ["American Water Heaters", "A. O. Smith Charlotte", "A. O. Smith Franklin"]},
    {"brand": "State Water Heaters", "parent": "A.O. Smith", "product": "Commercial, residential & tankless water heaters",
     "context": "water heater", "territory": "IA, NE, KS, MO, S IL",
     "db_aliases": ["State Water Heaters"]},

    # --- Aalberts Integrated Piping Systems ---
    {"brand": "Apollo Valves", "parent": "Aalberts Integrated Piping Systems", "product": "Commercial & industrial valves, pipe fittings",
     "context": "valves plumbing", "territory": "IA, NE, KS, MO, IL",
     "db_aliases": ["Apollo Valves"]},
    {"brand": "Shurjoint", "parent": "Aalberts Integrated Piping Systems", "product": "Grooved piping system",
     "context": "grooved piping", "territory": "IA, NE, KS, MO, IL",
     "db_aliases": ["Shurjoint"]},

    # --- American Bath Group ---
    {"brand": "Aker by Maax", "parent": "American Bath Group", "product": "Commercial & residential bathing fixtures",
     "context": "bath fixtures", "territory": "IA, NE, MO, S IL",
     "db_aliases": ["MAAX/AKER (American Bath Group)"]},
    {"brand": "Aquatic", "parent": "American Bath Group", "product": "Commercial & residential bathing fixtures",
     "context": "bath fixtures plumbing", "territory": "IA, NE, MO, C/S IL",
     "db_aliases": ["Aquatic (American Bath Group)"]},
    {"brand": "Bootz", "parent": "American Bath Group", "product": "Porcelain showers and bathtubs with surrounds",
     "context": "bathtub porcelain plumbing", "territory": "IA, NE, MO, C/S IL",
     "db_aliases": ["Bootz Industries"]},
    {"brand": "Comfort Designs", "parent": "American Bath Group", "product": "Commercial bathing fixtures",
     "context": "bathing fixtures plumbing", "territory": "IA, NE, MO, C/S IL",
     "db_aliases": ["Comfort Designs"]},
    {"brand": "MAAX", "parent": "American Bath Group", "product": "Commercial & residential bathing fixtures",
     "context": "bath fixtures", "territory": "IA, NE, MO, S IL",
     "db_aliases": ["MAAX/AKER (American Bath Group)"]},
    {"brand": "Maidstone", "parent": "American Bath Group", "product": "Kitchen and bathroom products",
     "context": "kitchen bath plumbing", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["Maidstone"]},
    {"brand": "Mr. Steam", "parent": "American Bath Group", "product": "Steam shower systems and accessories",
     "context": "steam shower", "territory": "IA, NE, KS, MO, S IL",
     "db_aliases": ["Mr. Steam (American Bath Group)"]},
    {"brand": "Salo", "parent": "American Bath Group", "product": "Commercial & residential bathing fixtures",
     "context": "bathing fixtures plumbing", "territory": "IA, NE",
     "db_aliases": ["Salo (American Bath Group)"]},

    # --- Single-brand partners ---
    {"brand": "Blanco", "parent": "Blanco", "product": "Kitchen solution provider",
     "context": "kitchen sinks faucets", "territory": "IA, NE, KS, MO, S IL",
     "db_aliases": ["BLANCO America, Inc."]},
    {"brand": "Braxton Harris", "parent": "Braxton Harris", "product": "Specialty plumbing supplies",
     "context": "plumbing supplies", "territory": "IA, NE, KS, MO, IL",
     "db_aliases": ["Braxton Harris"]},
    {"brand": "Elkhart", "parent": "Elkhart Products", "product": "Copper sweat/cast fittings",
     "context": "copper fittings plumbing", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["Elkhart Products Corporation"]},
    {"brand": "Harris", "parent": "Lincoln Electric", "product": "Brazing and solder alloys and equipment",
     "context": "brazing solder alloys", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["The Harris Products Group"]},
    {"brand": "Mill Rose", "parent": "Mill Rose Clean-Fit Products", "product": "Thread sealants, abrasives & chemical specialties",
     "context": "thread sealant plumbing", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["Mill-Rose Company"]},
    {"brand": "North Star", "parent": "North Star Water Treatment", "product": "Commercial & residential water treatment",
     "context": "water treatment softener", "territory": "IA, NE, KS, MO, IL",
     "db_aliases": ["North Star Water Treatment Systems", "BRM Sales / North Star"]},
    {"brand": "Pro-Flex", "parent": "Pro-Flex CSST", "product": "Gas CSST and hearth accessories",
     "context": "CSST gas piping", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["Pro-Flex, LLC"]},
    {"brand": "Rhomar", "parent": "Rhomar Water", "product": "Heat transfer fluids & hydronic system solutions",
     "context": "hydronic heat transfer fluid", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["Rhomar Water"]},
    {"brand": "Wesanco", "parent": "Wesanco ZSI", "product": "Strut, fittings, clamps, rooftop support systems",
     "context": "strut pipe support", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["Wesanco-ZSI"]},
    {"brand": "Zurn Pex", "parent": "Zurn", "product": "PEX plumbing and radiant solutions",
     "context": "PEX radiant plumbing", "territory": "IA, NE, MO, C/S IL",
     "db_aliases": ["Zurn Industries"]},

    # --- BRM Sales stock product (page 2) ---
    {"brand": "Armacell", "parent": None, "product": "Elastomeric foam and rubber pipe insulation",
     "context": "pipe insulation", "territory": "IA, NE, KS, MO, IL",
     "db_aliases": ["BRM Sales / Armacell"]},
    {"brand": "Blue Ribbon", "parent": None, "product": "Gauges and thermometers",
     "context": "gauges thermometers plumbing", "territory": "IA, NE, KS, MO, S IL",
     "db_aliases": ["BRM Sales / Blue Ribbon"]},
    {"brand": "CircuitSolver", "parent": None, "product": "Domestic hot water system balancing",
     "context": "hot water balancing valve", "territory": "KS, MO, S IL",
     "db_aliases": []},
    {"brand": "Fiat", "parent": None, "product": "Durable products from acrylic and terrazzo",
     "context": "mop sink terrazzo plumbing", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["BRM Sales / Fiat", "Fiat Manufacturing"]},
    {"brand": "Little Giant", "parent": None, "product": "Commercial & residential sump and sewage pumps",
     "context": "sump pump sewage", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["BRM Sales / Little Giant"]},
    {"brand": "Lang Recirc", "parent": None, "product": "Commercial and residential circulators",
     "context": "circulator pump hydronic", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["BRM Sales / Laing"]},
    {"brand": "Lawler Manufacturing", "parent": None, "product": "Tempered water mixing valves & systems",
     "context": "thermostatic mixing valve", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["BRM Sales / Lawler"]},
    {"brand": "Stingray", "parent": None, "product": "Tepid emergency solutions",
     "context": "emergency eyewash tepid water", "territory": "IA, NE, KS, MO, C/S IL",
     "db_aliases": ["BRM Sales / Stingray"]},
]

# Nathen's territory. A line card entry not sold here is excluded from his
# news feed (CircuitSolver is KS/MO/S IL only).
MY_STATES = ("NE", "IA")


def in_my_territory(entry):
    territory = entry.get("territory") or ""
    tokens = {t.strip().upper() for t in territory.replace("/", " ").split(",")}
    flat = " ".join(tokens)
    return any(state in flat for state in MY_STATES)


def active_lines():
    """Line card entries actually sold in Nebraska/Iowa."""
    return [e for e in LINE_CARD if in_my_territory(e)]


def parents():
    """Unique corporate partners worth tracking for corporate-level news."""
    seen = []
    for e in active_lines():
        p = e.get("parent")
        if p and p not in seen:
            seen.append(p)
    return seen


def alias_to_brand_name():
    """{crm_brand_name_lower: line_card_brand} for matching DB rows to the card."""
    out = {}
    for e in LINE_CARD:
        for alias in e.get("db_aliases", []):
            out[alias.strip().lower()] = e["brand"]
    return out


def find_entry(brand_name):
    """Look up a line card entry from either a card name or a CRM alias."""
    if not brand_name:
        return None
    needle = brand_name.strip().lower()
    for e in LINE_CARD:
        if e["brand"].strip().lower() == needle:
            return e
        for alias in e.get("db_aliases", []):
            if alias.strip().lower() == needle:
                return e
    return None
