# Degassing/Stripping Tower Design MCP Server
### PHREEQC-Based pH-Dependent Speciation with Perry's Handbook Heuristics

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://github.com/anthropics/mcp)
[![Tests Passing](https://img.shields.io/badge/tests-28%2F28%20passing-brightgreen.svg)](tests/)

## Current Status: Phase 1 Complete ✓ + Blower Sizing

**Tier 1 Heuristic Sizing** is fully implemented and tested:
- ✅ pH-dependent speciation (PHREEQC integration)
- ✅ Perry's Handbook correlations (Eckert GPDC, HTU/NTU)
- ✅ Tower diameter and height calculations
- ✅ Packing catalog with 9 standard packings
- ✅ **Blower sizing with Robbins pressure drop correlation**
- ✅ **Automatic blower type selection (Centrifugal/Rotary Lobe/Compressor)**
- ✅ **Complete pressure drop breakdown (7 components + safety factor)**
- ✅ **Discharge temperature and power consumption calculations**
- ✅ Fast (<1s) preliminary design for H₂S, CO₂, and VOC removal
- ✅ 28/28 tests passing (14 tower + 14 blower) including Perry's benchmarks
- ✅ MCP server operational with 2 tools

**Implementation Progress:**
- Phase 1 (Tier 1 Heuristic Sizing): ✅ **100% Complete**
- Phase 2 (Tier 2 PHREEQC Multi-Stage Simulation): 🔧 **85% Complete** (Functional, needs refinement)
- Phase 3 (Tier 3 WaterTAP Economic Costing): ⏳ 0% (Not Started)

See [REMAINING_IMPLEMENTATION_PLAN.md](REMAINING_IMPLEMENTATION_PLAN.md) for detailed roadmap.

---

## Technical Overview

This MCP server provides rigorous degassing and stripping tower design for water treatment applications, with particular emphasis on pH-dependent chemistry that critically affects removal efficiency.

### Key Innovation: pH-Dependent Speciation

The server implements **PHREEQC-based speciation** to accurately model the fraction of contaminant that can be air-stripped vs the fraction that remains as non-volatile ionic species:

**H₂S Stripping (pKa₁ = 7.0):**
- At pH 6.0: 89.6% strippable H₂S(aq), 10.4% non-strippable HS⁻
- At pH 7.8: 11.9% strippable H₂S(aq), 88.1% non-strippable HS⁻

**CO₂ Stripping (pKa₁ = 6.35):**
- At pH 6.0: 68.8% strippable CO₂(aq), 31.2% non-strippable HCO₃⁻
- At pH 8.0: 2.1% strippable CO₂(aq), 97.9% non-strippable HCO₃⁻/CO₃²⁻

This chemistry-aware approach prevents unrealistic removal predictions and correctly warns users when target outlet concentrations are unachievable without pH adjustment.

### Applications

1. **H₂S Removal (Sulfide Stripping)**
   - Groundwater and industrial wastewater treatment
   - Odor control and corrosion prevention
   - pH adjustment critical: Recommend pH 5.5-6.5 for optimal removal

2. **CO₂ Stripping (Alkalinity Removal)**
   - RO pretreatment to reduce scaling potential
   - Boiler feedwater alkalinity control
   - pH adjustment critical: Recommend pH 4.5-5.5 for maximum CO₂ conversion

3. **VOC Removal (Volatile Organic Stripping)**
   - Contaminated groundwater remediation (TCE, PCE, benzene)
   - Industrial wastewater treatment
   - No pH effects (neutral molecules)

---

## Quick Start

### Installation

```bash
# Clone repository
cd /mnt/c/Users/hvksh/mcp-servers/degasser-design-mcp

# Activate virtual environment (Python 3.12)
source ../venv312/bin/activate  # Linux/WSL
# OR
..\venv312\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

### MCP Server Configuration

Add to your MCP settings (e.g., Claude Desktop config):

```json
{
  "mcpServers": {
    "degasser-design-mcp": {
      "command": "/mnt/c/Users/hvksh/mcp-servers/venv312/Scripts/python.exe",
      "args": ["-m", "server"],
      "cwd": "/mnt/c/Users/hvksh/mcp-servers/degasser-design-mcp",
      "env": {}
    }
  }
}
```

### Available MCP Tools

#### 1. `heuristic_sizing` - Fast Tower Design (<1s)

Size a packed tower air stripper using Perry's Handbook correlations.

**Input Parameters:**
```python
{
  "application": "H2S",              # "H2S", "CO2", "VOC", or "general"
  "water_flow_rate_m3_h": 60.0,     # m³/h
  "inlet_concentration_mg_L": 32.0, # mg/L
  "outlet_concentration_mg_L": 0.05,# mg/L
  "air_water_ratio": 34.0,          # Volumetric ratio
  "temperature_c": 25.0,            # °C
  "water_ph": 6.0,                  # Required for H2S/CO2
  "packing_id": "Plastic_Pall_Rings_25mm"  # Optional
}
```

**Output (without blower sizing):**
```python
{
  "tower_diameter_m": 2.12,
  "tower_height_m": 4.94,
  "packing_height_m": 4.44,
  "packing_name": "Plastic Pall Rings",
  "packing_size_mm": 25.0,
  "design_velocity_m_s": 0.161,
  "flooding_velocity_m_s": 0.230,
  "ntu": 7.96,
  "htu_m": 0.465,
  "lambda_factor": 13.94,
  "removal_efficiency_percent": 99.97,
  "air_flow_rate_m3_h": 2040.0
}
```

**Output (with blower sizing - `include_blower_sizing=True`):**
```python
{
  "tower_diameter_m": 2.12,
  "tower_height_m": 4.94,
  "packing_height_m": 4.44,
  "packing_name": "Plastic Pall Rings",
  "packing_size_mm": 25.0,
  "design_velocity_m_s": 0.161,
  "flooding_velocity_m_s": 0.230,
  "ntu": 7.96,
  "htu_m": 0.465,
  "lambda_factor": 13.94,
  "removal_efficiency_percent": 99.97,
  "air_flow_rate_m3_h": 2040.0,

  "blower_specs": {
    // Pressure Drop Breakdown
    "packed_bed_pressure_drop_pa": 1823.4,
    "inlet_distributor_pressure_drop_pa": 249.1,
    "outlet_distributor_pressure_drop_pa": 249.1,
    "demister_pressure_drop_pa": 373.6,
    "momentum_losses_pa": 87.3,
    "ductwork_silencer_pressure_drop_pa": 182.3,
    "elevation_head_pa": 58.2,
    "safety_factor_pa": 362.2,
    "total_system_pressure_drop_pa": 3385.2,
    "total_system_pressure_drop_inches_h2o": 13.59,
    "total_system_pressure_drop_psig": 0.49,

    // Blower Selection
    "blower_type": "Multistage Centrifugal",
    "thermodynamic_model": "Isothermal",
    "compression_ratio": 1.033,
    "discharge_pressure_pa": 104710.2,
    "discharge_pressure_psig": 0.49,

    // Temperatures
    "inlet_temperature_c": 25.0,
    "discharge_temperature_c": 25.0,

    // Power Requirements
    "shaft_power_kw": 10.2,
    "motor_power_kw": 11.1,
    "motor_power_hp": 14.9,

    // Efficiencies
    "blower_efficiency": 0.70,
    "motor_efficiency": 0.92
  }
}
```

**Example Usage:**
```python
# Via MCP tool call
result = await mcp__degasser_design_mcp__heuristic_sizing(
    application="H2S",
    water_flow_rate_m3_h=60.0,
    inlet_concentration_mg_L=32.0,
    outlet_concentration_mg_L=0.05,
    air_water_ratio=34.0,
    water_ph=6.0,
    packing_id="Plastic_Pall_Rings_25mm"
)
```

#### 2. `list_available_packings` - Query Packing Catalog

List all available packings with specifications.

**Output:**
```python
{
  "packings": [
    {
      "packing_id": "Plastic_Pall_Rings_25mm",
      "name": "Plastic Pall Rings",
      "material": "Plastic",
      "nominal_size_mm": 25.0,
      "packing_factor_m_inv": 180.0,
      "surface_area_m2_m3": 206.0,
      "void_fraction": 0.90
    },
    ...
  ],
  "count": 9
}
```

---

## Design Methodology

### 1. pH-Dependent Speciation (PHREEQC)

For H₂S and CO₂ applications, PHREEQC calculates the equilibrium distribution between strippable and non-strippable species:

```
SOLUTION 1
  pH 6.0
  temp 25.0
  S(-2) 32.0 mg/L
END
```

**Speciation Calculation:**
```
α₀ = [H₂S] / ([H₂S] + [HS⁻] + [S²⁻])
```

Retrieved from PHREEQC:
```python
neutral_molality = solution.species_molalities['H2S']  # mol/kgw
total_molality = solution.total_element('S', units='mol')  # mol/kgw
strippable_fraction = neutral_molality / total_molality
```

**Critical Implementation Detail:**
- Species molalities return mol/kgw
- `total_element()` defaults to mmol (1000× error!)
- **Must specify `units='mol'`** to match units

### 2. Stripping Factor (λ)

**Perry's Equation 14-16:**
```
λ = H × (G/L)
```

Where:
- H = Henry's constant (dimensionless, Cgas/Caq)
- G/L = Air-to-water ratio (volumetric)

**Physical Meaning:** λ >> 1 indicates stripping is thermodynamically favorable.

### 3. Number of Transfer Units (NTU)

**Perry's Equation 14-19 (Colburn):**
```
NOG = ln[(Cin/Cout - 1/λ) / (1 - 1/λ)] / ln(λ)
```

### 4. Height of Transfer Unit (HTU)

**Perry's Equation 14-158 (Simplified empirical):**
```
HOG = f(packing_type, packing_size, flow_rates, Henry's_constant)
```

For Plastic Pall Rings 25mm: HOG ≈ 0.465 m

### 5. Packing Height

**Perry's Equation 14-15:**
```
Z = NOG × HOG × Safety_Factor
```

Typical safety factor: 1.20 (20% margin)

### 6. Tower Diameter (Eckert GPDC)

**Flow Parameter (Perry's Eq 14-140):**
```
FLG = (L/G) × √(ρG/ρL)
```

**Flooding Velocity (Perry's Eq 14-142):**
```
uflood = Csf × √[(ρL - ρG)/ρG] × √(ε/Fp)
```

Where:
- Csf = Capacity parameter at flooding (from Eckert chart, Fig 14-55)
- ε = Packing void fraction
- Fp = Packing factor

**Design Velocity:**
```
udesign = 0.70 × uflood  # 70% of flooding, 30% safety margin
```

**Tower Diameter:**
```
D = √(4QG / (π × udesign))
```

### 7. Blower Sizing & Pressure Drop

#### 7.1 Robbins Correlation for Packed Bed (Perry's Eq 14-145 to 14-151)

The server uses the **validated `fluids` library implementation** of the Robbins correlation for accurate packed bed pressure drop:

```python
from fluids.packed_tower import Robbins

ΔP_packed = Robbins(
    L=liquid_mass_velocity,  # kg/(s·m²)
    G=gas_mass_velocity,     # kg/(s·m²)
    rhol=1000.0,             # kg/m³
    rhog=1.2,                # kg/m³
    mul=0.001,               # Pa·s
    H=packing_height,        # m
    Fpd=packing_factor_dry   # ft⁻¹
)
```

**Validation**: Matches Perry's Example 13 within ±20% for 2-inch metal Pall rings.

#### 7.2 Seven Accessory Pressure Drop Components

Total system pressure drop includes:

1. **Packed Bed** (Robbins correlation): Dominant component (~50-60%)
2. **Inlet Vapor Distributor**: 0.5-1.5 inches H₂O (default 1.0)
3. **Outlet Vapor Distributor**: 0.5-1.5 inches H₂O (default 1.0)
4. **Demister/Coalescer Pads**: 1-2 inches H₂O clean (default 1.5)
5. **Entrance/Exit Momentum Losses**: 0.5·ρ·v² per abrupt change
6. **Ductwork and Silencers**: 5-15% of bed ΔP (default 10%)
7. **Tower Elevation Static Head**: ρ·g·H for gas column

**Safety Factor**: 12% added to total (industry standard)

**Total System Pressure Drop:**
```
ΔP_total = (ΔP₁ + ΔP₂ + ... + ΔP₇) × 1.12
```

#### 7.3 Automatic Blower Type Selection

Based on compression ratio β = P_discharge / P_inlet:

| Compression Ratio (β) | Pressure Range | Blower Type | Thermodynamic Model | Default η |
|-----------------------|----------------|-------------|---------------------|-----------|
| β ≤ 1.2 | ≤ 3 psig | Multistage Centrifugal | Isothermal | 70% |
| 1.2 < β ≤ 1.5 | 3-7 psig | Rotary Lobe (Roots) | Polytropic | 65% |
| β > 1.5 | > 7 psig | Single-Stage Compressor | Adiabatic | 75% |

**User Override**: Pass `blower_type_override` parameter to specify blower type explicitly.

#### 7.4 Power Calculations (fluids.compressible)

**Isothermal Power** (β ≤ 1.2):
```python
W = P₁ · Q · ln(P₂/P₁) / η
```
- Uses `fluids.compressible.isothermal_work_compression()`
- Assumes near-isothermal compression with cooling
- Discharge temperature ≈ inlet temperature

**Polytropic Power** (1.2 < β ≤ 1.5):
```python
n = polytropic_exponent(k=1.4, eta_p=η)  # Derives n from efficiency
W = (n/(n-1)) · P₁ · Q · [(P₂/P₁)^((n-1)/n) - 1] / η
T₂ = T₁ · [1 + (β^((n-1)/n) - 1) / η]
```
- Uses `fluids.compressible.isentropic_work_compression()` with polytropic exponent n
- Derives proper polytropic exponent n≈1.78 from efficiency (not γ=1.4)
- Uses `fluids.compressible.isentropic_T_rise_compression()` for discharge temperature
- Example: For β=1.34, η_p=0.65 → T₂≈88°C (63°C rise)

**Adiabatic Power** (β > 1.5):
```python
W = (γ/(γ-1)) · P₁ · Q · [(P₂/P₁)^((γ-1)/γ) - 1] / η
T₂ = T₁ + (T₂_isentropic - T₁) / η
```
- γ = 1.4 for air (ratio of specific heats Cp/Cv)
- Includes aftercooling heat duty calculation
- Significant temperature rise requires aftercooling

**Motor Power:**
```
P_motor = P_shaft / η_motor
```
Default motor efficiency: 92%

#### 7.5 Critical Dependencies

**Requires `fluids` library**:
```bash
pip install fluids
```

The blower sizing module **fails loudly** if fluids library is not installed:
```python
ImportError: fluids library is required for blower sizing calculations.
Install with: pip install fluids
```

No fallback calculations are provided to ensure deterministic, validated results.

#### 7.6 Efficiency Considerations

**Default Efficiencies** (from Perry's Handbook / GPSA Engineering Data Book):
- Multistage Centrifugal: 70% (range 65-80%)
- Rotary Lobe: 65% (range 60-70%)
- Single-Stage Compressor: 75% (range 70-85%)
- Electric Motor: 92% (range 90-95%)

**Best Practice for Final Design:**
1. **Preliminary Design**: Use default efficiencies (what this tool provides)
2. **Detailed Design**: Override with vendor data using `blower_efficiency_override` parameter
3. **Final Selection**: Verify with vendor selection software (Aerzen, Kaeser, Tuthill)

**Note**: Dynamic efficiency estimation requires proprietary vendor performance curves not available in open-source. Always verify preliminary estimates with actual vendor quotes.

---

## 8. When to Use Tier 1 vs Tier 2 vs Tier 3

### Decision Tree

```
START: Need to design a stripping tower
│
├─ Screening multiple options (>5 scenarios)?
│  ├─ YES → Use Tier 1 Heuristic (<1s per run)
│  │         Then down-select 2-3 candidates
│  └─ NO → Skip to Tier 2
│
├─ Operating conditions check:
│  ├─ pH ≥ 7.0 AND (H2S or CO2)?
│  │  └─ ⚠️ CRITICAL: Tier 1 will underestimate height 50-200%
│  │              → Must use Tier 2 for final design
│  │
│  ├─ Air/water ratio < 15?
│  │  └─ ⚠️ WARNING: Weak driving force, Tier 2 recommended
│  │
│  └─ High alkalinity (>500 mg/L CaCO3)?
│      └─ ⚠️ WARNING: Significant pH drift expected, use Tier 2
│
├─ Design fidelity required:
│  ├─ Preliminary sizing / feasibility → Tier 1 OK (with warnings)
│  ├─ Bid preparation / final design → Tier 2 REQUIRED
│  └─ Regulatory compliance / SAT → Tier 2 + Tier 3
│
└─ Economic optimization needed?
   └─ Tier 3 (OPEX vs CAPEX, acid dosing vs tower height)
```

### Tier 1: Fast Heuristic (<1s)

**Use when:**
- Screening >5 design alternatives
- pH 5.5-6.5 (acidified feed)
- Air/water ratio >20
- Preliminary feasibility study
- Ballpark cost estimate

**DO NOT use for final design if:**
- ⚠️  pH ≥ 7.0 (neutral/alkaline)
- ⚠️  Air/water ratio < 15
- ⚠️  High alkalinity (>500 mg/L)
- ⚠️  Bid preparation or regulatory submission

**Structured Warnings:**
Tier 1 returns `warnings` array in JSON output:
```json
{
  "warnings": [
    {
      "severity": "critical",
      "category": "ph_drift",
      "message": "Operating at pH 7.8 without acid control...",
      "recommendations": [
        "Acidify feed to pH 5.5-6.5 (reduces tower height 3-5×)",
        "Use Tier 2 simulation tool for accurate pH-coupled sizing"
      ],
      "estimated_error_range": "50-200% height underestimate"
    }
  ]
}
```

### Tier 2: pH-Coupled Simulation (10-30s) - FUNCTIONAL (85% Complete)

**Current Status:**
- ✅ Staged equilibrium with PHREEQC integration
- ✅ Counter-current flow simulation
- ✅ Murphree efficiency for partial equilibrium
- ✅ pH profile tracking through column
- ✅ Mass balance within 10% (target <1%)
- 🔧 Convergence for N<50 stages
- ⚠️ High stage counts (N>50) need convergence tuning

**Use when:**
- Operating at pH ≥ 7.0
- Need accurate pH drift prediction
- Evaluating acid dosing strategies
- Final design validation
- Off-gas scrubber sizing
- Regulatory compliance documentation

**Required inputs:**
- Same as Tier 1 plus:
- Number of theoretical stages (or auto-optimize)
- Murphree efficiency (default 0.85)
- Convergence tolerance (default 0.01)

**Current Capabilities:**
- Axial pH(z), C(z), y(z) profiles
- Stage-by-stage mass balance
- N2(g) carrier gas with Peng-Robinson EOS
- Fixed pressure operation (1 atm)
- VOC phases (TCE, CCl4) with critical properties

**Needs Refinement:**
- Exact G/L molar ratio calculation
- Kremser initialization for faster convergence
- Adaptive Murphree efficiency
- H2S/CO2 pH coupling validation

### Tier 3: Economic Optimization (5-10s) - NOT YET IMPLEMENTED

**Use when:**
- Comparing CAPEX vs OPEX tradeoffs
- Optimizing acid dosing vs tower height
- LCOW calculation
- Bid finalization

**Coming in Phase 3:**
- Tower vessel CAPEX
- Packing and installation costs
- Blower/pump CAPEX and OPEX
- Chemical costs (acid dosing)
- Levelized cost of water (LCOW)

---

## Packing Catalog

9 standard packings from Perry's Handbook Table 14-13:

| Packing | Material | Size (mm) | Fp (m⁻¹) | Surface Area (m²/m³) | Void Fraction |
|---------|----------|-----------|----------|---------------------|---------------|
| Plastic Pall Rings | Plastic | 25 | 180 | 206 | 0.90 |
| Plastic Pall Rings | Plastic | 50 | 85 | 102 | 0.92 |
| Metal Pall Rings | Metal | 25 | 220 | 220 | 0.75 |
| Metal Pall Rings | Metal | 38 | 164 | 164 | 0.78 |
| Metal Pall Rings | Metal | 50 | 121 | 121 | 0.78 |
| Ceramic Intalox Saddles | Ceramic | 25 | 256 | 302 | 0.73 |
| Ceramic Intalox Saddles | Ceramic | 50 | 118 | 131 | 0.76 |
| Ceramic Raschig Rings | Ceramic | 25 | 190 | 587 | 0.74 |
| Ceramic Raschig Rings | Ceramic | 50 | 92 | 213 | 0.74 |

**Selection Guidelines:**
- **H₂S/CO₂**: Use plastic or ceramic (corrosion-resistant)
- **VOC**: Plastic packing typically preferred
- **Smaller packing (25mm)**: Lower HTU (better efficiency), larger diameter, higher cost
- **Larger packing (50mm)**: Higher HTU, smaller diameter, lower cost

---

## Validation

### Test Suite: 28/28 Tests Passing ✓

**Tower Design Tests (14/14):**

**Perry's TCE Benchmark (test_tower_design.py:161):**
- Application: VOC (Trichloroethylene)
- Water flow: 100 m³/h
- TCE: 38 mg/L → 0.00151 mg/L (99.996% removal)
- Air/water ratio: 30:1
- **Result**: Tower design matches Perry's example within 5%

**PHREEQC Validation (test_voc_phases.py):**
- CO₂ gas-liquid equilibrium: ✓
- Custom VOC phases (TCE): ✓
- Henry's constant calculations: ✓

**pH-Dependent Speciation (utils/speciation.py):**
- H₂S speciation across pH 5-9: ✓
- CO₂ speciation across pH 5-9: ✓
- Units consistency (mol vs mmol): ✓

**Blower Sizing Tests (14/14):**

**Robbins Pressure Drop (test_blower_sizing.py):**
- Perry's Example 13 (2-inch Pall rings): Within ±20% ✓
- Regression against fluids library: <1% error ✓
- All 7 pressure drop components validated ✓

**Blower Type Selection:**
- Automatic selection by compression ratio: ✓
- User override with alias handling: ✓
- Correct thermodynamic model mapping: ✓

**Power Calculations (fluids.compressible):**
- Isothermal power (β ≤ 1.2): ✓
- Polytropic power with correct exponent (1.2 < β ≤ 1.5): ✓
- Discharge temperature validation (75-95°C for β=1.34): ✓
- Adiabatic power with aftercooling (β > 1.5): ✓

**Integration Tests:**
- H₂S stripping with blower sizing: ✓
- Optional blower sizing (on/off toggle): ✓
- Efficiency override functionality: ✓

---

## Architecture

### Three-Tier Design (Phase 1 Complete)

**✅ Tier 1: Fast Heuristic Sizing (<1 sec)**
- Perry's Handbook correlations
- PHREEQC speciation for H₂S/CO₂
- Tower diameter from Eckert GPDC
- Tower height from HTU/NTU method
- Packing selection and catalog
- Preliminary performance metrics

**⏳ Tier 2: PHREEQC Multi-Stage Simulation (10-30 sec)** - Not Implemented
- Multi-stage tower chemistry
- Interstage pH and temperature profiles
- Mass balance validation
- Gas-liquid equilibrium verification

**⏳ Tier 3: WaterTAP Economic Costing (5-10 sec)** - Not Implemented
- Tower vessel CAPEX
- Packing and installation costs
- Blower/pump CAPEX and OPEX
- Chemical costs (acid dosing)
- LCOW calculation

### Directory Structure

```
degasser-design-mcp/
├── .mcp.json                    # MCP server configuration
├── README.md                    # This file
├── REMAINING_IMPLEMENTATION_PLAN.md  # Detailed roadmap for Phases 2-3
├── server.py                    # FastMCP server implementation ✓
├── requirements.txt             # Python dependencies ✓
├── .env.example                 # Environment variable template ✓
├── .gitignore                   # Git ignore rules ✓
├── tools/                       # MCP tool implementations
│   ├── __init__.py              # ✓
│   ├── heuristic_sizing.py      # Tier 1 heuristic sizing ✓
│   └── schemas.py               # Pydantic validation models ✓
├── utils/                       # Utility modules
│   ├── __init__.py              # ✓
│   ├── tower_design.py          # Perry's correlations (diameter, height) ✓
│   ├── packing_properties.py    # Packing catalog interface ✓
│   ├── speciation.py            # PHREEQC pH-dependent speciation ✓
│   ├── henry_constants.py       # Henry's law database ✓
│   ├── helpers.py               # Eckert GPDC, HTU/NTU methods ✓
│   ├── pressure_drop.py         # Robbins correlation & accessory ΔP ✓
│   ├── blower_sizing.py         # Power calculations (fluids.compressible) ✓
│   └── import_helpers.py        # Dependency detection ✓
├── databases/                   # Design databases
│   ├── pack.json                # Packing specifications ✓
│   ├── henrys_law.db            # VOC Henry's constants ✓
│   ├── voc_phases.dat           # PHREEQC custom phases ✓
│   └── voc_properties.json      # VOC properties ✓
└── tests/                       # Unit and integration tests
    ├── test_tower_design.py     # Perry's benchmark validation ✓
    └── test_voc_phases.py       # PHREEQC integration tests ✓
```

---

## Example: H₂S Stripping at pH 6.0

```python
result = await heuristic_sizing(
    application="H2S",
    water_flow_rate_m3_h=60.0,
    inlet_concentration_mg_L=32.0,
    outlet_concentration_mg_L=0.05,
    air_water_ratio=34.0,
    temperature_c=25.0,
    water_ph=6.0,
    packing_id="Plastic_Pall_Rings_25mm"
)
```

**Results:**
```
Speciation (pH 6.0):
  Strippable H₂S: 89.6% (28.7 mg/L)
  Non-strippable HS⁻: 10.4% (3.3 mg/L)

Tower Design:
  Diameter: 2.12 m (7.0 ft)
  Height: 4.94 m (16.2 ft)
  Packing: Plastic Pall Rings 25mm (4.44 m depth)

Performance:
  Stripping factor (λ): 13.94
  Transfer units (NTU): 7.96
  HTU: 0.465 m
  Removal efficiency: 99.97% of strippable H₂S
  Actual outlet: ~3.3 mg/L (non-strippable HS⁻)

Operating Conditions:
  Air flow: 2,040 m³/h (1,200 CFM)
  Design velocity: 0.161 m/s (70% of flooding)
  Flooding margin: 30% safety factor
```

**Design Note:** At pH 6.0, only 89.6% of total sulfide is strippable. The remaining 3.3 mg/L HS⁻ is ionic and non-volatile. For complete sulfide removal, consider:
1. Lower pH to 5.5 (95% strippable)
2. Post-treatment oxidation (convert HS⁻ to SO₄²⁻)
3. Chemical precipitation

---

## References

1. **Perry's Chemical Engineers' Handbook, 8th Edition**
   - Section 14: Gas Absorption and Gas-Liquid System Design
   - Eckert GPDC: Figures 14-55, 14-56
   - HTU/NTU Method: Equations 14-15 to 14-22, 14-153, 14-158
   - Flooding correlations: Equations 14-140 to 14-142

2. **PHREEQC (Version 3)**
   - Parkhurst, D.L., and Appelo, C.A.J., 2013, Description of input and examples for PHREEQC version 3
   - USGS Techniques and Methods, book 6, chap. A43
   - phreeqpython: Python wrapper for PHREEQC

3. **Treybal, R.E. (1980)**
   - Mass Transfer Operations, 3rd Edition
   - McGraw-Hill

4. **Strigle, R.F. (1994)**
   - Packed Tower Design and Applications, 2nd Edition
   - Gulf Publishing Company

5. **fluids library (CalebBell/fluids)**
   - GitHub: https://github.com/CalebBell/fluids (402 stars)
   - Validated thermodynamic and fluid mechanics library for Python
   - Used for:
     - Robbins packed bed pressure drop correlation
     - Isothermal/polytropic/adiabatic compression calculations
     - Discharge temperature predictions
     - Polytropic exponent derivation from efficiency
   - Reference: Bell, C. (2016-2025). fluids: Open-source fluid properties library

6. **Robbins, L.A. (1991)**
   - "Improve Pressure-Drop Prediction with a New Correlation"
   - Chemical Engineering Progress, 87(5), 87-91
   - Basis for packed bed pressure drop calculations (Perry's Eq 14-145 to 14-151)

---

## License

MIT License - See LICENSE file for details

---

## Support

For technical issues or questions:
- GitHub Issues: https://github.com/puran-water/degasser-design-mcp/issues
- Email: hvkshetry@gmail.com

---

**Status**: Phase 1 (Tier 1 Heuristic Sizing) Complete ✓ | Ready for Phase 2 (PHREEQC Multi-Stage) and Phase 3 (WaterTAP Costing)
