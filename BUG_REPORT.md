# Bug Report - Degasser Design MCP Server

## Testing Date: 2025-01-16

### Test Environment
- Python: 3.12
- MCP Server: degasser-design-mcp
- Tools: heuristic_sizing, list_available_packings

## Bugs Found

### Critical Bugs

#### BUG-001: heuristic_sizing returns Tier1Outcome object instead of dict
- **Severity**: Critical (MCP tool unusable)
- **Error**: `Input should be a valid dictionary [type=dict_type, input_value=Tier1Outcome(...)]`
- **Root Cause**: Function returns `Tier1Outcome` object, but MCP framework expects dict
- **Impact**: Cannot use heuristic_sizing via MCP
- **Fix Required**: Need wrapper that returns `outcome.model_dump()` for MCP while preserving object for Tier 2
- **Constraint**: Cannot break Tier 2 which expects Tier1Outcome object

### Major Bugs

#### BUG-002: MCP wrapper needs explicit parameters (not **kwargs)
- **Severity**: Major (wrapper pattern issue)
- **Error**: `Field required [type=missing, input_value={'application': 'H2S'...}, input_type=dict]`
- **Root Cause**: MCP framework doesn't unpack **kwargs properly
- **Fix Applied**: Changed wrapper to explicit parameters
- **Status**: Fixed - wrapper now has full parameter signature

#### BUG-003: Tier1Outcome uses @dataclass, not Pydantic
- **Severity**: Major (serialization issue)
- **Error**: `'Tier1Outcome' object has no attribute 'model_dump'`
- **Root Cause**: Tier1Outcome is a dataclass, not a Pydantic BaseModel
- **Fix Applied**: Use `asdict()` from dataclasses instead of `model_dump()`
- **Status**: Fixed - using dataclasses.asdict()

### Minor Bugs

#### BUG-004: Invalid packing ID silently falls back to default
- **Severity**: Minor (silent fallback)
- **Test**: Provided invalid packing ID "Invalid_Packing_Name"
- **Expected**: Error message or warning
- **Actual**: Silently uses "Plastic_Pall_Rings_50mm" as default
- **Impact**: User may not realize their packing selection was ignored
- **Recommendation**: Add warning when packing ID not found

## Test Results Summary

### Successful Tests
1. **H2S Stripping (pH 6.0)**: ✅ Working correctly with blower sizing
2. **CO2 Stripping (pH 7.5)**: ✅ Correctly shows critical pH drift warning
3. **VOC Stripping**: ✅ Working correctly, no pH warnings (as expected)
4. **list_available_packings**: ✅ Returns all 9 packings correctly
5. **Outlet > Inlet validation**: ✅ Properly rejects invalid input
6. **Negative flow validation**: ✅ Properly rejects negative values
7. **High pH warning (H2S at pH 9)**: ✅ Shows critical warning with λ=0.10

### Test Log

### Test 1: Basic H2S Stripping
- **Time**: 2025-01-16
- **Input**: H2S, 100 m³/h, 50 mg/L → 0.1 mg/L, pH 6.0
- **Expected**: Tower dimensions with warnings if applicable
- **Result**: SUCCESS after BUG-001, BUG-002, BUG-003 fixes
- **Output**: Tower 2.18m dia × 10.46m height, 2.01 hp blower

### Test 2: CO2 with pH drift warning
- **Input**: CO2, 150 m³/h, 100 mg/L → 5 mg/L, pH 7.5
- **Result**: SUCCESS - Critical warning about pH drift (λ=1.43)
- **Output**: Tower 2.53m dia × 8.13m height, 2.42 hp blower

### Test 3: VOC stripping
- **Input**: VOC, 80 m³/h, 10 mg/L → 0.001 mg/L
- **Result**: SUCCESS - No pH warnings (correct for VOC)
- **Output**: Tower 2.81m dia × 3.89m height

### Test 4: Edge cases
- **Invalid packing**: Falls back to default (BUG-004)
- **Outlet > Inlet**: Proper validation error
- **Negative flow**: Proper validation error
- **H2S at pH 9**: Shows critical warning (λ=0.10)

## Tier 2 Testing (2025-01-16)

### Critical Bugs

#### BUG-005: Tier 2 needs more iterations to converge
- **Severity**: Major (fixable by increasing iterations)
- **Error**: `Counter-current flow did not converge after 50 iterations`
- **Solution**: Increased to 100 iterations in server.py
- **Results with 100 iterations**:
  - VOC (15 stages): ✅ Converged in 78 iterations, mass balance 1% error
  - H2S (auto-find): Still failed at 100 iterations (4.26% error)
  - H2S (20 stages): Converged in 71 iterations BUT...
- **Status**: Partially fixed - VOC works, H2S has issues

#### BUG-006: H2S mass balance completely wrong
- **Severity**: Critical (fundamental algorithm error)
- **Test**: H2S, 50 m³/h, 30→0.5 mg/L, pH 6.0, 20 stages
- **Symptoms**:
  - Mass balance error: 98.3% (essentially no stripping!)
  - pH rises from 6.0 to 8.6 (should stay near 6)
  - Liquid concentration stays at 30 mg/L throughout
  - Gas concentration near zero (1e-11 ppm)
  - Alpha_0 drops to 0.02 (only 2% strippable at pH 8.6)
- **Root Cause**: pH calculation appears broken - pH should not rise during H2S stripping
- **Impact**: H2S simulation gives nonsensical results

### Update 2025-01-16 (After Codex Fix)

#### Water Chemistry Fix Applied
Codex implemented comprehensive water chemistry support:
- **Created**: `utils/water_chemistry.py` module with RO MCP compatible ion parsing
- **Updated**: `equilibrium_stage()` to use background ions for charge balance
- **Added**: `water_chemistry_json` parameter to MCP tools (cross-MCP compatible)

#### Test Results After Fix

##### H2S Test (pH 6.0, 20 stages)
- **pH Behavior**: ✅ FIXED - pH stays 6.0-6.55 (not 8.6!)
- **Strippable fraction**: ✅ FIXED - α₀ stays 0.70-0.90 (not 0.02)
- **Convergence**: ✅ Converged in 73 iterations
- **Mass Balance**: ❌ STILL BROKEN - 98.3% error, essentially no mass transfer
- **Liquid Profile**: Stays at 30 mg/L throughout tower
- **Gas Profile**: Near zero (5.6×10⁻¹² ppm)

##### CO2 Test (pH 7.5, 15 stages)
- **Result**: ❌ Failed to converge after 100 iterations
- **Error**: 1.24% convergence error

##### VOC Test (TCE, 15 stages)
- **pH Behavior**: ✅ Stable at 7.0 (as expected, no pH effects)
- **Convergence**: ✅ Converged in 78 iterations
- **Mass Balance**: ✅ PERFECT - 0.016% error
- **Concentration Profile**: ✅ Correct exponential decay (10 → 0.001 mg/L)

#### Diagnosis
- **pH bug**: FIXED by water chemistry implementation
- **Mass transfer bug**: NEW ISSUE - H2S and CO2 not transferring to gas phase
- **VOC**: Working perfectly (no pH-dependent speciation)

#### Suspected New Issue
The mass balance tracking may be using wrong component names for H2S/CO2:
- Line 224 in simulation_sizing.py uses `AQUEOUS_TOTAL_COMPONENT_MAP`
- Mapping might be incorrect for H2S: using "S(-2)" vs "H2S"
- VOC works because "Tce" maps correctly

### Summary of Current Status
- **Combined MCP tool**: ✅ Successfully created and working
- **Tier 1 mode**: ✅ Works correctly with all applications
- **Tier 2 VOC**: ✅ PERFECT - Works with excellent mass balance
- **Tier 2 H2S pH bug**: ✅ FIXED - pH now stays realistic with water chemistry
- **Tier 2 H2S/CO2 mass transfer**: ❌ NEW BUG - No gas stripping occurring
- **Cross-MCP compatibility**: ✅ Water chemistry JSON format matches RO MCP

### Next Steps
1. Debug why H2S/CO2 aren't transferring to gas phase in PHREEQC
2. Check if `sol.total("S(-2)")` is the correct way to get total H2S
3. Verify gas phase definitions for H2S(g) and CO2(g)
4. Consider if the issue is with gas phase interaction or component tracking

### Recommendation
- Use Tier 1 for H2S/CO2 until Tier 2 mass transfer is fixed
- Tier 2 works perfectly for VOC applications
- Water chemistry integration is successful and cross-MCP compatible
