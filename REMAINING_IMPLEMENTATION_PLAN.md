# Remaining Implementation Plan
## Degasser Design MCP Server - Phases 2 & 3

**Document Version**: 1.0
**Date**: 2025-10-14
**Status**: Phase 1 Complete (100%) | Phase 2 Not Started (0%) | Phase 3 Not Started (0%)

---

## Executive Summary

This document outlines the remaining implementation work for the degasser-design-mcp server following the successful completion of Phase 1 (Tier 1 Heuristic Sizing).

**Completed (Phase 1):**
- ✅ pH-dependent speciation using PHREEQC
- ✅ Perry's Handbook heuristic correlations (Eckert GPDC, HTU/NTU)
- ✅ Tower diameter and height sizing
- ✅ Packing catalog (9 standard packings from Perry's Table 14-13)
- ✅ MCP server with 2 operational tools
- ✅ 14/14 tests passing including Perry's TCE benchmark
- ✅ Comprehensive documentation and example design report

**Remaining Work:**
- ⏳ **Phase 2**: PHREEQC Multi-Stage Tower Simulation (Tier 2)
- ⏳ **Phase 3**: WaterTAP Economic Costing (Tier 3)

---

## Phase 2: PHREEQC Multi-Stage Tower Simulation

**Objective**: Implement rigorous multi-stage tower chemistry simulation using PHREEQC to validate heuristic designs and provide detailed concentration/pH profiles.

**Target Duration**: 10-30 seconds per simulation
**Priority**: Medium (nice-to-have validation, not critical for preliminary design)

### 2.1 Technical Scope

#### Gas-Liquid Equilibrium Modeling

**H₂S System:**
```
SOLUTION 1  # Stage 1 (bottom)
  pH 6.0
  S(-2) 28.7 mg/L
  temp 25
END

EQUILIBRIUM_PHASES 1
  H2S(g) -5.0 10  # Log partial pressure, max moles to dissolve/degas
END

GAS_PHASE 1
  -fixed_pressure
  H2S(g) 0.0
  pressure 1.0  # atm
  volume 1.0
END
```

**CO₂ System:**
```
SOLUTION 1
  pH 5.0
  Alkalinity 100 mg/L as CaCO3
  temp 25
END

EQUILIBRIUM_PHASES 1
  CO2(g) -3.5 10
END

GAS_PHASE 1
  -fixed_pressure
  CO2(g) 0.0
  pressure 1.0
  volume 1.0
END
```

**VOC System:**
```
# Use custom phases from databases/voc_phases.dat
SOLUTION 1
  pH 7.0
  temp 25
END

PHASES
  TCE(g)
    C2HCl3 = C2HCl3
    -log_k -2.322559  # From Henry's constant H = 8.59
    -analytic ...
END

EQUILIBRIUM_PHASES 1
  TCE(g) -4.0 10
END
```

#### Multi-Stage Simulation Logic

**Stage-by-Stage Approach:**
1. Divide tower into N stages (typically 5-10 stages)
2. For each stage bottom-to-top:
   - Liquid enters from stage above (or feed at top)
   - Gas enters from stage below (or fresh air at bottom)
   - Equilibrate using PHREEQC
   - Extract outlet liquid composition → inlet to stage above
   - Extract outlet gas composition → inlet to stage below
3. Iterate until convergence (liquid and gas profiles stabilize)

**Convergence Criteria:**
- Change in outlet concentrations < 0.1% between iterations
- Maximum 20 iterations
- Warn if not converged

#### Output Profiles

**Per-Stage Data:**
- Liquid: pH, concentrations (H₂S/CO₂/VOC, HS⁻/HCO₃⁻, etc.), temperature
- Gas: partial pressures (H₂S(g), CO₂(g), etc.), total pressure
- Mass transfer: driving force (y - y*), stage efficiency

**Overall Performance:**
- Total removal efficiency
- Mass balance closure (inlet - outlet = stripped amount)
- Comparison to heuristic design predictions

### 2.2 Implementation Tasks

| Task | Description | Estimated Effort | Files |
|------|-------------|------------------|-------|
| **2.2.1** | Create `tools/phreeqc_simulator.py` | 3-4 hours | `tools/phreeqc_simulator.py` |
| | - MCP tool `simulate_degasser_phreeqc` | | `tools/schemas.py` (add models) |
| | - Input: tower config (N stages, geometry), water chemistry, gas composition | | |
| | - Output: stage-by-stage profiles, overall performance | | |
| **2.2.2** | Create `utils/phreeqc_client.py` | 2-3 hours | `utils/phreeqc_client.py` |
| | - PHREEQC input file generation | | |
| | - Stage equilibrium calculation | | |
| | - Output parsing (selected_output.txt) | | |
| **2.2.3** | Multi-stage iteration logic | 3-4 hours | `utils/multistage_solver.py` |
| | - Stage-by-stage equilibrium | | |
| | - Convergence checking | | |
| | - Mass balance validation | | |
| **2.2.4** | Integration with Tier 1 | 2 hours | `tools/heuristic_sizing.py` |
| | - Option to run Tier 2 validation after Tier 1 | | `server.py` |
| | - Pass heuristic design to PHREEQC simulator | | |
| **2.2.5** | Testing | 3-4 hours | `tests/test_phreeqc_simulator.py` |
| | - H₂S case at pH 6.0 | | `tests/test_multistage.py` |
| | - CO₂ case at pH 5.0 | | |
| | - VOC case (TCE) | | |
| | - Mass balance closure validation | | |

**Total Estimated Effort**: 13-17 hours

### 2.3 Acceptance Criteria

- [ ] MCP tool `simulate_degasser_phreeqc` operational
- [ ] Multi-stage simulation converges within 20 iterations
- [ ] Mass balance closes within 1% error
- [ ] Stage profiles show physically realistic trends (pH, concentrations)
- [ ] Comparison with Tier 1 heuristic design within 10% on removal efficiency
- [ ] Test suite passes for H₂S, CO₂, and VOC cases

### 2.4 Known Challenges

**Challenge 1: PHREEQC Convergence Issues**
- **Risk**: PHREEQC may not converge for extreme pH or very high/low gas pressures
- **Mitigation**: Add bounds checking, use -force_equality, provide reasonable initial guesses

**Challenge 2: Gas-Phase Mass Transfer**
- **Issue**: PHREEQC assumes equilibrium, but real towers have mass transfer resistance
- **Mitigation**: Adjust stage efficiency based on Murphree efficiency or HTU/HETP from Tier 1

**Challenge 3**: Performance (10-30 sec target)
- **Risk**: N-stage simulation with iteration may exceed 30 seconds
- **Mitigation**: Start with N=5 stages, use caching, optimize PHREEQC calls

### 2.5 Success Metrics

- Simulation completes in < 30 seconds for typical case (5-10 stages)
- Provides value-added insight beyond Tier 1 (e.g., pH profile, interstage concentrations)
- Validates Tier 1 design or suggests modifications

---

## Phase 3: WaterTAP Economic Costing

**Objective**: Implement economic analysis using WaterTAP framework to estimate CAPEX, OPEX, and LCOW.

**Target Duration**: 5-10 seconds per costing
**Priority**: High (essential for engineering decision-making)

### 3.1 Technical Scope

#### WaterTAP Costing Blocks

**Tower Vessel Costing** (EPA WBS 3.3 - Degasifier):
```python
from watertap.costing import WaterTAPCosting
from watertap.unit_models.degasser import Degasser

# Tower vessel
degasser_unit.costing = WaterTAPCosting()
degasser_unit.costing.cost_degasser(
    degasser_type="packed_tower",
    diameter_m=2.12,
    height_m=4.94,
    material="FRP"  # Fiberglass reinforced plastic
)
```

**Packing Costing**:
```python
# Random packing
packing_cost = (
    packing_volume_m3
    × packing_unit_cost_per_m3
    × installation_factor
)

# Packing unit costs (2025 USD/m³):
# - Plastic Pall Rings 25mm: $800-1200/m³
# - Plastic Pall Rings 50mm: $600-900/m³
# - Ceramic Intalox Saddles: $1200-1800/m³
# - Metal Pall Rings: $2000-3000/m³
```

**Blower Costing**:
```python
from watertap.unit_models.compressor import Compressor

blower_unit.costing = WaterTAPCosting()
blower_unit.costing.cost_compressor(
    flow_rate_m3_s=0.567,  # 2040 m³/h
    pressure_rise_pa=10000,  # 10 kPa (packing pressure drop)
    efficiency=0.75
)
```

**Chemical Costing** (Acid for pH adjustment):
```python
# Acid requirement: Titration to target pH
# H2SO4: ~$50-100/ton
# HCl: ~$100-150/ton

acid_dose_kg_per_m3 = calculate_acid_dose(
    inlet_ph=7.8,
    target_ph=6.0,
    alkalinity_mg_L=100
)

annual_acid_cost = (
    acid_dose_kg_per_m3
    × water_flow_m3_per_year
    × acid_unit_cost_per_kg
)
```

#### LCOW Calculation

**Levelized Cost of Water (LCOW)**:
```
LCOW ($/m³) = (CAPEX × CRF + Annual OPEX) / Annual Water Treated

Where:
- CRF = Capital Recovery Factor = i(1+i)ⁿ / [(1+i)ⁿ - 1]
- i = Discount rate (typically 5-8%)
- n = Project lifetime (typically 20-30 years)
```

**CAPEX Breakdown**:
- Tower vessel (material, fabrication, delivery)
- Packing (material, installation)
- Blower (equipment, motor, installation)
- Instrumentation (pH meters, flow meters, pressure transmitters)
- Piping and valves
- Electrical and controls
- Site preparation and civil works
- Engineering and procurement (15-20% of equipment)
- Contingency (10-20%)

**OPEX Breakdown**:
- Electricity (blower power)
- Chemical costs (acid)
- Maintenance and replacement
  - Packing replacement (every 5-10 years)
  - Blower maintenance (annual)
- Labor (operation and maintenance)
- Miscellaneous (utilities, insurance)

### 3.2 Implementation Tasks

| Task | Description | Estimated Effort | Files |
|------|-------------|------------------|-------|
| **3.2.1** | Create `tools/watertap_costing.py` | 4-5 hours | `tools/watertap_costing.py` |
| | - MCP tool `cost_degasser_watertap` | | `tools/schemas.py` (add models) |
| | - Input: tower config from Tier 1, material selection, location factors | | |
| | - Output: CAPEX, OPEX, LCOW breakdown | | |
| **3.2.2** | WaterTAP flowsheet setup | 3-4 hours | `utils/watertap_flowsheet.py` |
| | - Define degasser unit model | | |
| | - Define blower/compressor | | |
| | - Define chemical addition (acid) | | |
| | - Connect units in flowsheet | | |
| **3.2.3** | Costing parameter database | 2-3 hours | `databases/costing_params.json` |
| | - Packing unit costs by type | | |
| | - Material factors (FRP vs SS vs concrete) | | |
| | - Regional cost adjustments (CEPCI) | | |
| | - Chemical unit costs | | |
| **3.2.4** | Integration with Tier 1 | 2 hours | `tools/heuristic_sizing.py` |
| | - Option to run Tier 3 costing after Tier 1 | | `server.py` |
| | - Pass tower design to WaterTAP costing | | |
| **3.2.5** | Sensitivity analysis | 3-4 hours | `utils/sensitivity.py` |
| | - Vary discount rate (3-10%) | | |
| | - Vary electricity cost ($0.05-0.15/kWh) | | |
| | - Vary chemical cost (±50%) | | |
| | - Generate tornado plots | | |
| **3.2.6** | Testing | 3-4 hours | `tests/test_watertap_costing.py` |
| | - H₂S case: Compare to industry benchmarks | | |
| | - CO₂ case: Validate against published data | | |
| | - VOC case: Check reasonableness | | |

**Total Estimated Effort**: 17-23 hours

### 3.3 Acceptance Criteria

- [ ] MCP tool `cost_degasser_watertap` operational
- [ ] CAPEX breakdown by component (vessel, packing, blower, etc.)
- [ ] OPEX breakdown by category (electricity, chemicals, maintenance)
- [ ] LCOW calculation with configurable assumptions (discount rate, lifetime)
- [ ] Sensitivity analysis shows impact of key cost drivers
- [ ] Results within ±30% of published industry data for similar projects
- [ ] Test suite validates costing logic

### 3.4 Known Challenges

**Challenge 1: WaterTAP Degasser Model Availability**
- **Risk**: WaterTAP may not have a pre-built degasser costing model
- **Mitigation**: Use generic vessel costing, adapt from similar unit models (gas absorption tower)

**Challenge 2: Regional Cost Variations**
- **Issue**: Costs vary significantly by location (labor, materials, regulations)
- **Mitigation**: Use CEPCI adjustment factors, allow user to specify location multiplier

**Challenge 3: Packing Cost Data**
- **Issue**: Packing costs are vendor-specific and not always public
- **Mitigation**: Use ranges from Strigle (1994) and vendor quotes, update with CEPCI

### 3.5 Success Metrics

- Costing completes in < 10 seconds
- LCOW estimates are within ±30% of industry benchmarks
- Provides actionable insight for project feasibility decisions
- Sensitivity analysis identifies key cost drivers (e.g., electricity, packing replacement frequency)

---

## Phase 4: Report Generation (Optional Enhancement)

**Objective**: Generate professional HTML/PDF reports with design calculations, performance curves, and economic summaries.

**Priority**: Low (documentation and presentation, not core functionality)

### 4.1 Scope

- Professional HTML report template
- Auto-generated design calculations (show work, not just results)
- Performance curves (removal efficiency vs air/water ratio, pH effects)
- Economic summary tables and charts
- Exportable to PDF for client deliverables

### 4.2 Implementation Tasks

| Task | Estimated Effort |
|------|------------------|
| Create `tools/report_generator.py` | 4-5 hours |
| HTML template with Jinja2 | 3-4 hours |
| Charts and plots (matplotlib/plotly) | 3-4 hours |
| PDF export (weasyprint or reportlab) | 2-3 hours |
| Testing and examples | 2-3 hours |

**Total Estimated Effort**: 14-19 hours

**Status**: Deferred to future release

---

## Implementation Priorities

### Recommended Sequence

**High Priority (Phase 3 - WaterTAP Costing):**
- Essential for engineering decision-making
- Provides immediate value (LCOW for feasibility studies)
- Relatively straightforward integration with WaterTAP framework
- **Effort**: ~17-23 hours
- **Value**: Very High

**Medium Priority (Phase 2 - PHREEQC Multi-Stage):**
- Validation and refinement of Tier 1 designs
- Provides detailed chemistry insight (pH profiles, speciation)
- More complex (iterative convergence, mass balance)
- **Effort**: ~13-17 hours
- **Value**: Medium (nice-to-have for validation)

**Low Priority (Phase 4 - Report Generation):**
- Documentation and presentation
- Can be achieved with existing tools (Markdown → PDF)
- Less critical than economic analysis
- **Effort**: ~14-19 hours
- **Value**: Low-Medium (improves user experience)

### Suggested Order

1. **Phase 3** (WaterTAP Costing) - High value, moderate effort
2. **Phase 2** (PHREEQC Multi-Stage) - Validation and refinement
3. **Phase 4** (Report Generation) - Polish and user experience

---

## Dependencies and Prerequisites

### Phase 2 Dependencies

**Software:**
- PHREEQC 3.8+ (already installed via phreeqpython)
- phreeqpython 1.5+ (already in requirements.txt)

**Data:**
- Gas phase definitions (H₂S(g), CO₂(g) - built-in to PHREEQC)
- Custom VOC phases (already created in databases/voc_phases.dat)

**Knowledge:**
- PHREEQC SELECTED_OUTPUT syntax
- Multi-stage equilibrium modeling
- Mass balance closure techniques

### Phase 3 Dependencies

**Software:**
- WaterTAP 0.11+ (needs to be added to requirements.txt)
- Pyomo 6.7+ (WaterTAP dependency)
- IDAES PSE 2.2+ (WaterTAP dependency)

**Data:**
- Equipment cost correlations (EPA WBS)
- Regional cost factors (CEPCI)
- Packing costs (Strigle 1994, vendor data)
- Chemical costs (market prices)

**Knowledge:**
- WaterTAP costing framework
- EPA Work Breakdown Structure (WBS)
- Chemical Engineering Plant Cost Index (CEPCI)

---

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| WaterTAP degasser model unavailable | High | Medium | Use generic vessel model, adapt from similar units |
| PHREEQC convergence issues | Medium | Medium | Add bounds checking, use reasonable initial guesses |
| Performance targets missed (>30s Tier 2, >10s Tier 3) | Medium | Low | Optimize PHREEQC calls, use caching, profile code |
| Cost data outdated or unavailable | Medium | Low | Use ranges, update with CEPCI, allow user overrides |
| Integration complexity with existing Tier 1 | Low | Low | Design clean interfaces, maintain modularity |

---

## Testing Strategy

### Phase 2 Testing

**Unit Tests:**
- PHREEQC input generation (correct syntax)
- Output parsing (extract values correctly)
- Mass balance calculation (inlet - outlet)

**Integration Tests:**
- H₂S case (5 stages, pH 6.0, convergence)
- CO₂ case (5 stages, pH 5.0, convergence)
- VOC case (5 stages, TCE, equilibrium)

**Validation:**
- Compare to published multi-stage simulation data
- Check mass balance closure (< 1% error)
- Verify physically realistic profiles

### Phase 3 Testing

**Unit Tests:**
- CAPEX calculation (each component)
- OPEX calculation (each category)
- LCOW calculation (CRF, annual costs)

**Integration Tests:**
- Full costing workflow (Tier 1 → Tier 3)
- Sensitivity analysis (vary assumptions)

**Validation:**
- Compare to industry benchmarks (±30%)
- Check unit cost reasonableness
- Verify sensitivity trends

---

## Success Criteria (Overall)

**Phase 2 (PHREEQC Multi-Stage) Complete When:**
- ✅ Multi-stage simulation converges for H₂S, CO₂, VOC cases
- ✅ Mass balance closes within 1%
- ✅ Execution time < 30 seconds
- ✅ Test suite passes
- ✅ Documentation complete

**Phase 3 (WaterTAP Costing) Complete When:**
- ✅ CAPEX, OPEX, LCOW calculated correctly
- ✅ Results within ±30% of industry data
- ✅ Sensitivity analysis functional
- ✅ Execution time < 10 seconds
- ✅ Test suite passes
- ✅ Documentation complete

**Overall Project Complete When:**
- ✅ All three tiers operational (Tier 1 ✓, Tier 2, Tier 3)
- ✅ Full workflow: Heuristic → Simulation → Costing
- ✅ MCP server with 4-5 tools
- ✅ Comprehensive test coverage (>80%)
- ✅ Professional documentation
- ✅ Example design reports

---

## Timeline Estimate

**Assuming full-time effort (8 hours/day):**

| Phase | Effort (hours) | Duration (days) | Start After |
|-------|----------------|-----------------|-------------|
| Phase 3 (WaterTAP Costing) | 17-23 | 3 days | Phase 1 complete |
| Phase 2 (PHREEQC Multi-Stage) | 13-17 | 2 days | Phase 3 complete |
| Phase 4 (Report Generation) | 14-19 | 2-3 days | Phase 2 complete |

**Total**: ~7-8 days of full-time development

**Assuming part-time effort (2-4 hours/day):**
- **Phase 3**: 1-2 weeks
- **Phase 2**: 1 week
- **Phase 4**: 1-2 weeks

**Total**: ~3-5 weeks part-time

---

## Next Steps

### Immediate Actions

1. **Decision on Priority**: Confirm Phase 3 (WaterTAP Costing) as next priority
2. **WaterTAP Setup**: Add WaterTAP to requirements.txt, verify installation
3. **Cost Data Collection**: Gather packing costs, material factors, CEPCI data
4. **Kickoff Phase 3**: Begin implementation of `tools/watertap_costing.py`

### Long-Term Vision

- **Phase 5**: GUI/Web Interface (Streamlit or React)
- **Phase 6**: Optimization Module (Pyomo-based tower optimization)
- **Phase 7**: Integration with other treatment MCP servers (RO, IX, etc.)

---

## Document Maintenance

**Update Frequency**: After each phase completion
**Owner**: Project Lead
**Review**: Technical team before each phase kickoff

**Version History**:
- v1.0 (2025-10-14): Initial plan following Phase 1 completion

---

**End of Document**
