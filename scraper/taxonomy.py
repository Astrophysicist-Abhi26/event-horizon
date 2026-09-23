"""
Event Horizon taxonomy and interest profile.

Everything that decides *what an event is about* and *how much it matters to
you* lives in this one file. Edit freely.

Structure
---------
FIELDS      top-level fields, in display order (Cosmology first on purpose)
SUBFIELDS   sub-field id -> (parent field, label, relevance weight)
RULES       sub-field id -> list of regex patterns (word-boundary safe)
DECLARED    subject codes that *organisers* attach to events (arXiv-style
            researchseminars topics, INSPIRE categories, ai-deadlines tags)
            -> sub-fields. Declared codes are the most trustworthy evidence.
PROTOTYPES  one-paragraph descriptions of each sub-field, used by the
            embedding classifier (Option B) to catch events with no keywords.
"""

import re

# ---------------------------------------------------------------------------
# Fields and sub-fields
# ---------------------------------------------------------------------------
FIELDS = {
    "cosmo":   "Cosmology",
    "astro":   "Astrophysics",
    "ai":      "AI / ML",
    "math":    "Mathematics",
    "physics": "Physics",
}

# id: (parent, label, weight). Weight = how much an event on this topic
# matters to you, 0-100, before bonuses. Cosmology is deliberately highest.
SUBFIELDS = {
    "cosmo.de":      ("cosmo", "Dark energy & expansion", 68),
    "cosmo.lss":     ("cosmo", "Large-scale structure & surveys", 64),
    "cosmo.early":   ("cosmo", "CMB & early universe", 62),
    "cosmo.dm":      ("cosmo", "Dark matter", 60),
    "cosmo.general": ("cosmo", "Cosmology (general)", 60),

    "ai.science":    ("ai", "ML for science", 52),
    "ai.theory":     ("ai", "ML theory", 40),
    "ai.general":    ("ai", "AI / ML (general)", 30),

    "astro.he":       ("astro", "High-energy, compact objects & GW", 40),
    "astro.galactic": ("astro", "Galaxies & AGN", 40),
    "astro.stellar":  ("astro", "Stars, Sun & planets", 32),
    "astro.general":  ("astro", "Astronomy (general)", 36),

    "math.nt":        ("math", "Number theory", 34),
    "math.topology":  ("math", "Topology", 34),
    "math.algebra":   ("math", "Algebra & representation theory", 32),
    "math.geometry":  ("math", "Geometry", 30),
    "math.probability": ("math", "Probability & statistics", 32),
    "math.mathphys":  ("math", "Mathematical physics", 30),
    "math.analysis":  ("math", "Analysis & PDE", 24),
    "math.other":     ("math", "Other mathematics", 20),

    "phys.gr":       ("physics", "Gravitation & GR", 40),
    "phys.hepth":    ("physics", "High-energy theory & QFT", 28),
    "phys.quantum":  ("physics", "Quantum physics", 18),
    "phys.condmat":  ("physics", "Condensed matter & stat mech", 12),
    "phys.fluids":   ("physics", "Fluids, plasma & climate", 12),
    "phys.general":  ("physics", "Physics (other)", 10),
}

# Bonuses applied on top of the best single weight (see score_event)
BONUS_COSMO_X_AI = 25        # your research intersection
BONUS_ASTRO_X_AI = 18
BONUS_COSMO_X_STATS = 10     # cosmology x inference / statistics
BONUS_SECOND_FIELD = 0.25    # fraction of the best *other-field* weight
BONUS_BENGALURU = 10
BONUS_INDIA = 5
BONUS_SCHOOL = 5             # schools/workshops are high value for a PhD student

# Default relevance threshold used for notifications (the website default is
# lower; you control it with the slider).
NOTIFY_MIN_SCORE = 45
URGENT_MIN_SCORE = 80        # these trigger an immediate notification

# ---------------------------------------------------------------------------
# Keyword rules. All patterns are case-insensitive and word-bounded unless the
# pattern says otherwise. Patterns starting with "CS:" are case-sensitive
# (for acronyms like AI, SBI, DESI that collide with ordinary words).
# ---------------------------------------------------------------------------
W = r"\b"
RULES = {
    "cosmo.general": [
        r"cosmolog\w*", r"cosmic (?:web|expansion|history|structure)",
        r"big bang", r"lambda-?cdm", r"CS:ΛCDM", r"CS:LCDM", r"friedmann",
        r"CS:FLRW", r"standard model of cosmology", r"primordial universe",
    ],
    "cosmo.de": [
        r"dark energy", r"cosmic acceleration", r"accelerat\w* expansion",
        r"hubble (?:tension|constant|parameter)", r"CS:H_?0 tension",
        r"expansion history", r"quintessence", r"phantom (?:crossing|dark|divide|regime)",
        r"CS:w0-?wa", r"CS:w_0", r"dynamical dark", r"modified gravity",
        r"CS:f\(R\)", r"horndeski", r"type ia supernova\w*", r"supernova cosmology",
        r"cosmic chronometer\w*", r"distance ladder",
    ],
    "cosmo.early": [
        r"inflation(?:ary)?", r"cosmic microwave background", r"CS:CMB",
        r"primordial", r"early universe", r"reioni[sz]ation", r"21[- ]?cm",
        r"cosmic dawn", r"dark ages", r"baryogenesis", r"non-?gaussianit\w*",
        r"cosmological collider", r"big bang nucleosynthesis", r"CS:BBN",
        r"planck (?:data|satellite|mission|collaboration)", r"b-modes?",
        r"stochastic gravitational[- ]wave background",
    ],
    "cosmo.lss": [
        r"large[- ]scale structure", r"CS:LSS", r"baryon acoustic", r"CS:BAO",
        r"galaxy (?:clustering|survey\w*|bias)", r"redshift[- ]space", r"CS:RSD",
        r"weak (?:gravitational )?lensing", r"cosmic shear", r"CS:DESI",
        r"CS:Euclid", r"CS:LSST", r"rubin observatory", r"CS:S8", r"sigma_?8",
        r"matter power spectrum", r"halo model", r"n-body", r"cosmological simulation\w*",
        r"structure formation", r"intensity mapping", r"peculiar velocit\w*",
        r"field-level", r"CS:Roman Space Telescope",
    ],
    "cosmo.dm": [
        r"dark matter", r"CS:WIMPs?", r"axion\w*", r"sterile neutrino\w*",
        r"fuzzy dark", r"primordial black holes?", r"CS:PBHs?", r"dark sector",
    ],

    "ai.general": [
        r"machine learning", r"deep learning", r"neural networks?",
        r"artificial intelligence", r"CS:AI", r"CS:LLMs?", r"large language models?",
        r"transformers?(?! (?:substation|winding))", r"generative models?",
        r"diffusion models?", r"reinforcement learning", r"computer vision",
        r"natural language processing", r"CS:NLP", r"representation learning",
        r"foundation models?", r"data science", r"agentic", r"graph neural",
        r"CS:GNNs?", r"CS:ML", r"neural information processing",
        r"learning representations", r"CS:NeurIPS", r"CS:ICML", r"CS:ICLR",
    ],
    "ai.theory": [
        r"learning theory", r"statistical learning", r"generali[sz]ation (?:bounds?|error|theory)",
        r"CS:PAC", r"kernel methods?", r"stochastic gradient", r"CS:SGD",
        r"neural tangent", r"(?:theory|mathematics) of (?:deep|machine) learning",
        r"deep learning theory", r"high-dimensional statistic\w*", r"sample complexity",
        r"online learning", r"bandits?", r"kolmogorov[- ]arnold", r"CS:KANs?",
        r"overparameteri[sz]\w*", r"implicit bias", r"compressed sensing",
        r"sparse recovery", r"bayesian (?:deep learning|neural)", r"optimal transport",
        r"mean[- ]field (?:limit|theory) of (?:neural|deep)",
    ],
    "ai.science": [
        r"(?:machine learning|deep learning|neural networks?|CS_INLINE_AI|artificial intelligence) "
        r"(?:for|in|and|meets)(?: and (?:for|in))? (?:the )?(?:science|physics|astronomy|astrophysics|cosmology|"
        r"physical sciences|astro\w*|space|the universe|fundamental physics)",
        r"CS:ML4PS", r"CS:AI4Science", r"ai for science", r"scientific machine learning",
        r"CS:SciML", r"physics[- ]informed", r"CS:PINNs?", r"neural operators?",
        r"simulation[- ]based inference", r"CS:SBI", r"likelihood[- ]free",
        r"emulat(?:or|ors|ion)", r"surrogate models?", r"neural (?:posterior|density|likelihood) estimat\w*",
        r"normali[sz]ing flows?", r"differentiable (?:simulation|programming|physics)",
        r"symbolic regression", r"data-driven discovery", r"astroinformatics",
        r"astrostatistic\w*", r"cosmostatistic\w*",
    ],

    "astro.general": [
        r"astronom\w*", r"astrophysic\w*", r"telescopes?", r"observator(?:y|ies)",
        r"astroparticle", r"radio astronomy", r"CS:SKA", r"sky surveys?", r"CS:IAU",
        r"space mission\w*", r"astrometr\w*", r"spectroscop\w* survey",
    ],
    "astro.galactic": [
        r"galax(?:y|ies)", r"galactic", r"CS:AGNs?", r"active galactic", r"quasars?",
        r"interstellar medium", r"CS:ISM", r"circumgalactic", r"milky way",
        r"star formation", r"intracluster", r"galaxy clusters?", r"star clusters?",
    ],
    "astro.stellar": [
        r"stellar", r"exoplanet\w*", r"planetary (?:system|science|formation)\w*",
        r"protoplanetary", r"asteroseismolog\w*", r"solar (?:physics|flares?|wind|corona|dynamo|system)",
        r"heliophys\w*", r"white dwarfs?", r"binary stars?", r"supernova(?:e|s)?",
        r"nucleosynthesis", r"small bodies", r"comets?", r"asteroids?", r"space weather",
        r"massive stars?", r"stars and planets", r"CS:Aditya",
    ],
    "astro.he": [
        r"black holes?", r"neutron stars?", r"pulsars?", r"magnetars?",
        r"gamma[- ]rays?", r"x-ray (?:astronomy|binar\w*|sources?|observ\w*)",
        r"cosmic rays?", r"gravitational[- ]waves?", r"CS:LIGO", r"CS:LISA",
        r"fast radio bursts?", r"CS:FRBs?", r"astrophysical transients", r"time[- ]domain",
        r"tidal disruption", r"kilonova\w*", r"compact objects?", r"accretion",
        r"CS:GRBs?", r"multi-?messenger", r"relativistic jets?",
        r"(?:hybrid|compact|quark|strange|neutron) stars?", r"dense matter", r"relativistic astrophysics",
    ],

    "math.nt": [
        r"number theor\w*", r"arithmetic (?:geometry|statistics|topology|of)",
        r"modular forms?", r"automorphic", r"CS:L-functions?", r"l-functions?",
        r"zeta (?:functions?|values)", r"diophantine", r"galois representations?",
        r"elliptic curves?", r"p-adic", r"iwasawa", r"langlands", r"class field",
        r"eisenstein", r"abelian variet\w*", r"(?:cubic|quadratic|number) fields",
        r"analytic number", r"sieve methods?", r"mahler measure", r"modularity",
        r"primes?(?! minister)", r"hecke", r"shimura", r"ramanujan", r"stark units?",
        r"(?:cubic|quadratic|abelian|galois|cyclotomic) extensions?", r"additive bases",
        r"h-bases", r"arithmetic statistics", r"CS:CM-types?", r"complex multiplication",
    ],
    "math.topology": [
        r"topolog\w*(?! (?:insulator|phase|order|matter|superconduct|quantum|photonic|materials))",
        r"homotop\w*", r"homolog\w*", r"cohomolog\w*", r"knots?(?! per)", r"knot theory",
        r"manifolds?", r"CS:TQFTs?", r"cobordism", r"fundamental groups?",
        r"mapping class", r"[34]-manifolds?", r"sheaf|sheaves", r"persistent homology",
        r"loop spaces?",
    ],
    "math.algebra": [
        r"algebras?(?! for tensors)", r"algebraic(?! (?:geometry|topology|number))", r"group theor\w*",
        r"group (?:schemes?|actions?|representations?|cohomology)",
        r"(?:finite|lie|free|discrete|abelian|reductive|algebraic|quantum) groups?",
        r"representation theor\w*", r"commutative algebra", r"noncommutative",
        r"rings? and modules", r"lie (?:algebras?|groups?|theory)", r"category theor\w*",
        r"categorical", r"hopf", r"quivers?", r"homological algebra", r"galois theory",
        r"cluster algebras?", r"operads?", r"koszul", r"vertex operator", r"2-groups?",
    ],
    "math.geometry": [
        r"geometr(?:y|ies|ic)(?! deep learning)", r"algebraic geometry", r"differential geometry",
        r"riemannian", r"symplectic", r"calabi[- ]yau", r"moduli", r"curvature",
        r"minimal surfaces?", r"hodge", r"k(?:ä|a)hler", r"mirror symmetry", r"spinors?",
        r"monopoles?", r"orbifolds?", r"varieties", r"surfaces of",
    ],
    "math.analysis": [
        r"(?:functional|harmonic|complex|real|fourier|microlocal|spectral|nonlinear|numerical) analysis",
        r"partial differential equations?", r"CS:PDEs?", r"differential equations?",
        r"operator (?:algebras?|theory)", r"heat kernels?", r"dirichlet forms?", r"sobolev",
        r"inequalit(?:y|ies)", r"dispersive", r"navier[- ]stokes", r"calculus of variations",
        r"approximation theory", r"integral (?:equations?|representations?)", r"analytification",
        r"amenab\w*", r"ergodic", r"schr(?:ö|o)dinger equations?", r"blow-?up",
    ],
    "math.probability": [
        r"probabilit\w*", r"stochastic\w*", r"random (?:matri\w*|walks?|graphs?|fields?|processes)",
        r"brownian", r"markov", r"martingales?",
        r"statistic\w*(?! (?:mechanic|physic))", r"bayesian", r"statistical inference",
        r"causal inference", r"large deviations?", r"percolation", r"extreme values?",
        r"fokker[- ]planck", r"regression", r"monte carlo", r"uncertainty quantification",
        r"spin glass\w*",
    ],
    "math.mathphys": [
        r"mathematical physics", r"integrable (?:systems?|models?|hierarch\w*)",
        r"lax (?:pairs?|representation)", r"conformal field theor\w*", r"vertex algebras?",
        r"CS:TQFTs?", r"mathematical relativity", r"spectral theory",
        r"quantum field theor\w* (?:mathematic\w*|rigorous)",
    ],
    "math.other": [
        r"mathemat\w*", r"combinatori\w*", r"graph theor\w*", r"mathematical logic",
        r"model theory", r"set theory", r"g(?:ö|o)del", r"incompleteness", r"proof theory",
        r"dynamical systems?", r"game theory", r"optimal control", r"convex optimi[sz]ation",
        r"numerical methods?", r"information theor\w*", r"coding theory", r"cryptograph\w*",
        r"formal(?:i[sz]ed|i[sz]ation)? (?:proofs?|mathematics)", r"theorem prov\w*",
        r"CS:Lean", r"posets?", r"history of mathematics", r"chaos",
    ],

    "phys.gr": [
        r"general relativity", r"gravitation\w*", r"gravity", r"spacetimes?", r"space-time",
        r"einstein", r"wormholes?", r"numerical relativity", r"quantum gravity",
        r"tidal deformation", r"geodesics?", r"black holes?", r"CS:gr-qc",
    ],
    "phys.hepth": [
        r"string theor\w*", r"string field", r"worldsheet", r"superstrings?",
        r"quantum field theor\w*", r"CS:QFTs?", r"gauge theor\w*", r"supersymmetr\w*",
        r"CS:SUSY", r"holograph\w*", r"CS:AdS", r"CS:CFTs?", r"conformal (?:field|bootstrap)",
        r"scattering amplitudes?", r"infrared divergences?", r"generali[sz]ed symmetr\w*",
        r"higher[- ]form symmetr\w*", r"higher symmetr\w*", r"particle physics",
        r"high[- ]energy physics", r"CS:HEP", r"phenomenolog\w*", r"colliders?",
        r"CS:LHC", r"neutrinos?", r"standard model", r"beyond the standard model",
        r"CS:BSM", r"effective field theor\w*", r"CS:EFTs?", r"CS:QCD", r"hadron\w*",
        r"swampland", r"anomal(?:y|ies) (?:inflow|matching)", r"nambu",
    ],
    "phys.quantum": [
        r"quantum (?:information|computing|computation|matter|many-body|chaos|optics|"
        r"mechanics|entanglement|technolog\w*|devices?|sensing|simulation|thermodynamics)",
        r"entanglement", r"qubits?", r"open quantum", r"decoherence", r"semiclassical",
        r"classical and quantum",
    ],
    "phys.condmat": [
        r"condensed matter", r"spin glass\w*", r"statistical (?:mechanics|physics)",
        r"phase transitions?", r"topological (?:insulators?|phases?|matter|order)",
        r"superconduct\w*", r"(?:frustrated|quantum|itinerant) magnetism", r"magnetic materials", r"spin (?:chains?|liquids?|systems?)",
        r"soft matter", r"active matter", r"living matter", r"polymers?",
        r"biological physics", r"biophysics", r"non-?equilibrium", r"many-body",
        r"glass(?:es|y)?(?! ceiling)", r"fluctuation theory", r"quantum matter",
    ],
    "phys.fluids": [
        r"turbulen\w*", r"fluids?", r"plasmas?", r"hydrodynamic\w*",
        r"magnetohydrodynamic\w*", r"CS:MHD", r"convection",
        r"(?<!normalizing )(?<!normalising )flows?", r"climate (?:dynamics|physics|model\w*|chaos)", r"atmospher\w*",
        r"ocean\w*", r"stochasticity", r"diffusion(?! models?)",
    ],
    "phys.general": [
        r"physics", r"optic(?:s|al)", r"photon\w*", r"lasers?",
        r"nuclear (?:physics|structure|theory|matter)", r"atomic", r"acoustic\w*",
        r"polari[sz]ation", r"caustics", r"water",
    ],
}

# ---------------------------------------------------------------------------
# Declared subject codes -> sub-fields (with evidence weight)
# Codes are normalised: lowercase, '.', '-', ' ' -> '_'.
# ---------------------------------------------------------------------------
STRONG, MEDIUM, WEAK = 1.5, 1.0, 0.6

_ARXIV_MATH = {
    "nt": "math.nt",
    "at": "math.topology", "gt": "math.topology", "gn": "math.topology",
    "kt": "math.topology",
    "ra": "math.algebra", "ac": "math.algebra", "rt": "math.algebra",
    "gr": "math.algebra", "qa": "math.algebra", "ct": "math.algebra",
    "ag": "math.geometry", "dg": "math.geometry", "mg": "math.geometry",
    "sg": "math.geometry", "cv": "math.analysis",
    "ap": "math.analysis", "ca": "math.analysis", "fa": "math.analysis",
    "oa": "math.analysis", "sp": "math.analysis", "na": "math.analysis",
    "pr": "math.probability", "st": "math.probability",
    "mp": "math.mathphys",
    "ds": "math.other", "co": "math.other", "lo": "math.other", "oc": "math.other",
    "it": "math.other", "gm": "math.other", "ho": "math.other",
}


def declared_codes(code):
    """Map one declared subject code -> list of (subfield, weight)."""
    raw = str(code).strip()
    if raw.startswith("field:"):             # chosen by YOU in watchlist.yaml
        f = raw[6:].strip()
        if f in SUBFIELDS:
            return [(f, STRONG)]
        if f in FIELDS:
            return [(next(s for s, v in SUBFIELDS.items()
                          if v[0] == f and s.endswith((".general", ".other"))), STRONG)]
        raw = f
    c = re.sub(r"[.\- ]+", "_", raw.lower())
    out = []
    # arXiv-style math codes: math_NT, math.NT
    m = re.match(r"^math_([a-z]{2})$", c)
    if m and m.group(1) in _ARXIV_MATH:
        return [(_ARXIV_MATH[m.group(1)], STRONG)]
    if c in ("math", "mathematics"):
        return [("math.other", WEAK)]
    if c in ("math_ph", "math_mp", "physics_math_ph", "math_and_math_physics"):
        return [("math.mathphys", STRONG)]
    # astro
    if c in ("astro_ph_co", "astro_co", "physics_astro_ph_co", "cosmology",
             "cosmology_and_nongalactic_astrophysics"):
        return [("cosmo.general", STRONG), ("astro.general", WEAK)]
    if c in ("astro_ph_ga", "astro_ga", "physics_astro_ph_ga"):
        return [("astro.galactic", STRONG)]
    if c in ("astro_ph_he", "astro_he", "physics_astro_ph_he"):
        return [("astro.he", STRONG)]
    if c in ("astro_ph_sr", "astro_ph_ep", "astro_sr", "astro_ep",
             "physics_astro_ph_sr", "physics_astro_ph_ep"):
        return [("astro.stellar", STRONG)]
    if c in ("astro_ph_im", "astro_im", "physics_astro_ph_im"):
        return [("astro.general", STRONG)]
    if c.startswith("astro") or c == "astrophysics":
        return [("astro.general", STRONG)]
    # physics
    if c in ("gr_qc", "physics_gr_qc", "general_relativity"):
        return [("phys.gr", STRONG)]
    if c == "gravitation_and_cosmology":           # INSPIRE category
        return [("phys.gr", STRONG), ("cosmo.general", WEAK)]
    if c in ("hep_th", "physics_hep_th", "theory_hep", "hep_ph", "physics_hep_ph",
             "phenomenology_hep", "hep_lat", "lattice"):
        return [("phys.hepth", STRONG)]
    if c in ("hep_ex", "experiment_hep", "experiment_nucl", "theory_nucl",
             "nucl_th", "nucl_ex", "general_physics", "physics_optics",
             "physics_atom_ph", "instrumentation", "accelerators"):
        return [("phys.general", MEDIUM)]
    if c in ("quant_ph", "physics_quant_ph", "quantum_physics"):
        return [("phys.quantum", STRONG)]
    if c.startswith(("cond_mat", "physics_cond_mat")) or c == "condensed_matter":
        return [("phys.condmat", STRONG)]
    if c in ("physics_flu_dyn", "physics_plasm_ph", "physics_ao_ph", "nlin_cd"):
        return [("phys.fluids", STRONG)]
    if c.startswith("nlin"):
        return [("math.mathphys", MEDIUM)]
    if c in ("physics",):
        return [("phys.general", WEAK)]
    if c == "data_analysis_and_statistics":        # INSPIRE category
        return [("math.probability", WEAK)]
    # CS / stats / AI
    if c in ("stat_ml", "cs_lg_theory", "optimization_methods", "learning_theory"):
        return [("ai.theory", STRONG)]
    if c in ("cs_lg", "cs_ai", "cs_ne", "machine_learning", "deep_learning",
             "representation_learning", "reinforcement_learning",
             "large_language_models", "lifelong_learning", "cs_cv", "cs_cl",
             "computer_vision", "natural_language_processing"):
        return [("ai.general", STRONG)]
    if c in ("stat", "stat_th", "stat_me", "stat_ap", "stat_co", "math_st"):
        return [("math.probability", STRONG)]
    if c in ("cs_it",):
        return [("math.other", MEDIUM)]
    return out


# ---------------------------------------------------------------------------
# Embedding prototypes (Option B). A few sentences that describe what an
# event on this sub-field *sounds like*. Negative classes absorb events that
# are about something else entirely, so they don't get forced into a field.
# ---------------------------------------------------------------------------
PROTOTYPES = {
    "cosmo.de": "dark energy, cosmic acceleration, Hubble tension, expansion history of the universe, modified gravity, supernova cosmology, DESI BAO constraints on w0 wa",
    "cosmo.lss": "large-scale structure of the universe, galaxy clustering, weak lensing, cosmic shear, redshift surveys, cosmological N-body simulations, matter power spectrum",
    "cosmo.early": "cosmic microwave background, inflation, primordial non-Gaussianity, reionization, 21-cm cosmology, early universe physics",
    "cosmo.dm": "dark matter particles, axions, primordial black holes, dark matter halos and direct detection",
    "cosmo.general": "cosmology conference, physical cosmology, the standard cosmological model, observational cosmology",
    "ai.science": "machine learning for physics and astronomy, simulation-based inference, neural emulators, AI for science, physics-informed neural networks",
    "ai.theory": "theory of deep learning, statistical learning theory, generalization bounds, optimization, kernel methods, learning theory",
    "ai.general": "machine learning conference, deep learning, large language models, neural networks, computer vision, natural language processing",
    "astro.he": "black holes, neutron stars, pulsars, gravitational wave astronomy, gamma-ray bursts, high-energy astrophysics, transients",
    "astro.galactic": "galaxy formation and evolution, active galactic nuclei, interstellar medium, star formation, galaxy clusters",
    "astro.stellar": "stellar physics, the Sun, solar flares, exoplanets, planetary systems, asteroseismology, supernovae",
    "astro.general": "astronomy and astrophysics meeting, telescopes, observatories, sky surveys, radio astronomy",
    "math.nt": "number theory, modular forms, L-functions, elliptic curves, Galois representations, arithmetic geometry, primes",
    "math.topology": "algebraic topology, low-dimensional topology, homotopy theory, knots, manifolds, cohomology",
    "math.algebra": "algebra, representation theory, group theory, Lie algebras, category theory, commutative algebra",
    "math.geometry": "differential geometry, algebraic geometry, symplectic geometry, moduli spaces, Riemannian geometry",
    "math.probability": "probability theory, stochastic processes, random matrices, Brownian motion, mathematical statistics, Bayesian inference",
    "math.mathphys": "mathematical physics, integrable systems, conformal field theory, rigorous quantum field theory",
    "math.analysis": "analysis, partial differential equations, harmonic analysis, functional analysis, operator theory",
    "math.other": "combinatorics, mathematical logic, dynamical systems, graph theory, discrete mathematics",
    "phys.gr": "general relativity, gravitation, spacetime geometry, black hole physics, numerical relativity, quantum gravity",
    "phys.hepth": "string theory, quantum field theory, particle physics, holography, scattering amplitudes, gauge theories",
    "phys.quantum": "quantum information, quantum computing, entanglement, quantum many-body physics, quantum optics",
    "phys.condmat": "condensed matter physics, statistical mechanics, soft matter, active matter, phase transitions, superconductivity",
    "phys.fluids": "fluid dynamics, turbulence, plasma physics, magnetohydrodynamics, climate and atmospheric physics",
    "phys.general": "physics colloquium, optics, lasers, atomic and nuclear physics",
}
NEGATIVE_PROTOTYPES = {
    "neg.bio": "biology, medicine, genomics, neuroscience, cell biology, clinical research, ecology",
    "neg.chem": "chemistry, materials synthesis, catalysis, batteries, chemical engineering",
    "neg.eng": "robotics, human-computer interaction, computer graphics, software engineering, web systems, information retrieval, electrical engineering",
    "neg.admin": "committee meeting, foundation day, cultural event, open day, inauguration ceremony, administrative announcement, alumni event",
    "neg.humanities": "history, philosophy, economics, social sciences, education policy, arts and culture",
}


# ---------------------------------------------------------------------------
# Compilation helpers
# ---------------------------------------------------------------------------
def _compile(pattern):
    if pattern.startswith("CS:"):
        return re.compile(W + pattern[3:] + W)
    pattern = pattern.replace("CS_INLINE_AI", "AI")
    return re.compile(W + "(?:" + pattern + ")" + W, re.I)


COMPILED = {sf: [_compile(p) for p in pats] for sf, pats in RULES.items()}


def parent(sf):
    return SUBFIELDS[sf][0]


def export_for_frontend():
    """The site builds its field/sub-field filter from this, so the
    taxonomy is defined in exactly one place."""
    return {
        "fields": [{"id": f, "label": lbl,
                    "subfields": [{"id": sf, "label": v[1]}
                                  for sf, v in SUBFIELDS.items() if v[0] == f]}
                   for f, lbl in FIELDS.items()],
    }
