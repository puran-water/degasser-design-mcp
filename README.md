# Degassing/Stripping Tower Design MCP Server

Air stripping tower design tool implementing Perry's Handbook correlations with PHREEQC geochemical speciation.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://github.com/anthropics/mcp)

## Implementation Status

### Tier 1: Heuristic Sizing (Complete)
- Perry's Handbook correlations (Eckert GPDC, HTU/NTU methods)
- PHREEQC integration for pH-dependent speciation
- Robbins pressure drop correlation for packed beds
- Blower type selection and power calculations
- 9 standard packings from Perry's Table 14-13
- Execution time: <1 second

### Tier 2: Staged Column Simulation (Complete ✅)
- PHREEQC equilibrium stage calculations
- Counter-current flow with adaptive Murphree efficiency
- Mass balance closure: <1% (VOC, CO2), <10% (H2S)
- Convergence stable for N<50 stages (200 iteration limit)
- pH-coupled speciation with water chemistry integration
- Execution time: 10-30 seconds

### Tier 3: Economic Optimization (Not Started)
- Planned: WaterTAP integration for costing
- Tower CAPEX, packing costs, utilities OPEX
- Levelized cost optimization

## Technical Overview

The server calculates packed tower dimensions for air stripping applications accounting for pH-dependent aqueous speciation. For weak acids (H₂S, CO₂), only the neutral molecular form is strippable while ionic species remain in solution.

### pH-Dependent Speciation

**H₂S System (pKa₁ = 7.0):**
- pH 6.0: α₀ = 0.896 (89.6% H₂S, 10.4% HS⁻)
- pH 7.0: α₀ = 0.500 (50% H₂S, 50% HS⁻)
- pH 8.0: α₀ = 0.091 (9.1% H₂S, 90.9% HS⁻)

**CO₂ System (pKa₁ = 6.35):**
- pH 6.0: α₀ = 0.688 (68.8% CO₂, 31.2% HCO₃⁻)
- pH 7.0: α₀ = 0.184 (18.4% CO₂, 81.6% HCO₃⁻)
- pH 8.0: α₀ = 0.022 (2.2% CO₂, 97.8% HCO₃⁻)

The strippable fraction α₀ is calculated using PHREEQC equilibrium modeling and applied to the effective Henry's constant.

### Applications

- **H₂S Removal**: Groundwater treatment, odor control. Requires pH < 6.5 for effective stripping.
- **CO₂ Stripping**: RO pretreatment, alkalinity reduction. Requires pH < 5.5 for >90% conversion.
- **VOC Removal**: Groundwater remediation (TCE, PCE). pH-independent for neutral compounds.

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

#### 2. `combined_simulation_mcp` - Tier 1 + Optional Tier 2

Run fast heuristic sizing (Tier 1) and optionally continue with rigorous PHREEQC simulation (Tier 2).

**Input Parameters:**
```python
{
  "application": "H2S",
  "water_flow_rate_m3_h": 50.0,
  "inlet_concentration_mg_L": 30.0,
  "outlet_concentration_mg_L": 0.5,
  "air_water_ratio": 40.0,
  "temperature_c": 25.0,
  "water_ph": 6.0,
  "run_tier2": true,                    # Set to true for Tier 2 simulation
  "num_stages_initial": 20,             # Fixed stage count (or None for auto-find)
  "find_optimal_stages": false          # If true, uses bisection to find optimal N
}
```

**Output (with Tier 2):**
```python
{
  "request": {...},                      # Echo of input parameters
  "result": {...},                       # Tier 1 results (tower dimensions, blower)
  "tier2": {
    "tower_height_m": 22.6,
    "theoretical_stages": 20,
    "HETP_m": 1.13,
    "stage_profiles": {
      "liquid_conc_mg_L": [...],        # Concentration profile (N+1 points)
      "gas_conc_ppm": [...],
      "pH": [...],                       # pH profile showing drift
      "alpha_0": [...]                   # Strippable fraction at each stage
    },
    "convergence_info": {
      "inner_iterations": 98,
      "converged": true,
      "mass_balance": {
        "mass_in_mg_h": 1500000.0,
        "mass_out_water_mg_h": 461985.2,
        "mass_stripped_mg_h": 1148197.9,
        "error_fraction": 0.073,         # 7.3% error
        "passed": "True"
      }
    }
  }
}
```

#### 3. `list_available_packings` - Query Packing Catalog

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

### 1. Speciation Calculation

PHREEQC calculates equilibrium speciation for pH-dependent systems:

```python
# PHREEQC solution definition
solution = pp.add_solution({'pH': 6.0, 'temp': 25.0, 'S(-2)': 32.0})

# Calculate strippable fraction
α₀ = solution.species_molalities['H2S'] / solution.total_element('S', units='mol')
```

Note: `total_element()` requires `units='mol'` to avoid unit mismatch with species_molalities (mol/kgw).

### 2. Tower Height Calculation

**Stripping Factor** (Perry's Eq. 14-16):
```
λ = H_eff × (G/L)    where H_eff = H × α₀
```

**Number of Transfer Units** (Perry's Eq. 14-19, Colburn):
```
NOG = ln[(Cin/Cout - 1/λ) / (1 - 1/λ)] / ln(λ)
```

**Packing Height** (Perry's Eq. 14-15):
```
Z = NOG × HOG × 1.2    (20% safety factor)
```

HTU values from empirical correlations or vendor data (typical: 0.3-1.0 m)

### 3. Tower Diameter (Eckert GPDC)

**Flooding Velocity** (Perry's Eq. 14-142):
```
uflood = Csf × √[(ρL - ρG)/ρG] × √(ε/Fp)
```
Where Csf from Eckert chart (Fig. 14-55) based on flow parameter FLG = (L/G)√(ρG/ρL)

**Design Conditions**:
- Operating velocity: 70% of flooding
- Tower diameter: D = √(4QG/(π × udesign))

### 4. Pressure Drop and Blower Sizing

**Packed Bed** (Robbins correlation, Perry's Eq. 14-145):
```python
ΔP_packed = Robbins(L, G, rhol, rhog, mul, H, Fpd)  # fluids library
```

**System Components**:
- Packed bed (50-60% of total)
- Distributors: 1.0" H₂O each (inlet/outlet)
- Demister: 1.5" H₂O
- Momentum losses, ductwork, elevation head
- Total system ΔP × 1.12 safety factor

**Blower Selection**:

| β | Pressure | Type | Model | η |
|---|----------|------|-------|---|
| ≤1.2 | ≤3 psig | Centrifugal | Isothermal | 70% |
| 1.2-1.5 | 3-7 psig | Rotary Lobe | Polytropic | 65% |
| >1.5 | >7 psig | Compressor | Adiabatic | 75% |

**Power Calculations**:
- Isothermal (β ≤ 1.2): W = P₁Q·ln(P₂/P₁)/η
- Polytropic (1.2 < β ≤ 1.5): Uses polytropic exponent n from efficiency
- Adiabatic (β > 1.5): Standard adiabatic compression with γ=1.4

Motor sizing includes 92% motor efficiency. Vendor data should be used for final design.

---

## Design Tool Selection

### Tier 1: Heuristic Sizing
**Use for**: Preliminary design, screening alternatives
**Limitations**:
- Assumes constant pH throughout tower
- May underestimate height by 50-200% for pH > 7.0 with H₂S/CO₂
- Not suitable for bid preparation

**Warnings issued when**:
- pH ≥ 7.0 for H₂S or CO₂ applications
- Air/water ratio < 15 (weak driving force)
- Alkalinity > 500 mg/L CaCO₃

### Tier 2: Staged Simulation (Complete ✅)
**Use for**: Final design when pH effects are significant
**Features**:
- Stage-by-stage pH and concentration profiles
- Counter-current flow with adaptive Murphree efficiency
- PHREEQC equilibrium at each stage
- Water chemistry integration (RO MCP compatible)

**Performance**:
- VOC: 0.004% mass balance error (production-ready)
- CO2: 0.13% mass balance error (pH 7.5 supported)
- H2S: 7.3% mass balance error (acceptable for engineering design)
- Convergence stable up to 50 stages with 200 iteration limit

### Tier 3: Economic Optimization (Not Implemented)
**Planned**: CAPEX/OPEX optimization via WaterTAP integration

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

**Test Coverage**: 28 tests passing

- Perry's TCE benchmark (38 → 0.00151 mg/L): Within 5% of handbook
- PHREEQC speciation for H₂S and CO₂: Validated across pH 5-9
- Robbins pressure drop: <1% error vs fluids library
- Blower power calculations: Validated against thermodynamic models

---

## Architecture

**Three-Tier Design**:
1. **Tier 1**: Perry's correlations with PHREEQC speciation (Complete ✅)
2. **Tier 2**: Equilibrium stage simulation (Complete ✅)
3. **Tier 3**: Economic optimization via WaterTAP (Planned)

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

## Example Usage

```python
# H₂S stripping at pH 6.0
result = await heuristic_sizing(
    application="H2S",
    water_flow_rate_m3_h=60.0,
    inlet_concentration_mg_L=32.0,
    outlet_concentration_mg_L=0.05,
    air_water_ratio=34.0,
    water_ph=6.0
)

# Results
# Tower: 2.12 m dia × 4.94 m height
# Packing: 4.44 m depth
# Air flow: 2,040 m³/h
# Strippable fraction at pH 6.0: 89.6%
```

Note: At pH 6.0, 10.4% of sulfide remains as non-strippable HS⁻. Lower pH to 5.5 for >95% removal.

---

## References

1. Perry's Chemical Engineers' Handbook, 8th Edition, Section 14
2. PHREEQC Version 3 (Parkhurst & Appelo, 2013), USGS
3. fluids library (CalebBell/fluids) for thermodynamics and pressure drop
4. Robbins, L.A. (1991), Chemical Engineering Progress, 87(5), 87-91

## License

MIT License

## Contact

GitHub: https://github.com/puran-water/degasser-design-mcp
