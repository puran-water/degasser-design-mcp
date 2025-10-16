"""
Test VOC PHREEQC phases definitions.

Validates that generated voc_phases.dat works correctly with phreeqpython
and produces expected gas-liquid equilibrium.

Reference: water-chemistry-mcp test patterns
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check for phreeqpython availability
try:
    from phreeqpython import PhreeqPython
    PHREEQPYTHON_AVAILABLE = True
except ImportError:
    PHREEQPYTHON_AVAILABLE = False


@pytest.mark.skipif(not PHREEQPYTHON_AVAILABLE, reason="PhreeqPython not available")
class TestVOCPhases:
    """Test suite for VOC PHREEQC phases."""

    @pytest.fixture
    def pp(self):
        """Create PhreeqPython instance with default database."""
        return PhreeqPython()

    @pytest.fixture
    def pp_with_voc(self):
        """
        Create PhreeqPython instance with VOC phases.

        Uses runtime database extension via pp.run_string() as recommended by Codex.
        This is more reliable than INCLUDE$ for custom phases.
        """
        # Create PhreeqPython with default database
        pp = PhreeqPython()

        # Add VOC species and phases at runtime
        # Per Codex: Use numeric GFW in 4th column to bypass formula parsing
        # Format: Element Species Alk GFW ElementGFW
        voc_definitions = """
SOLUTION_MASTER_SPECIES
    Tce     Tce     0   131.388   131.388
    Ct      Ct      0   153.823   153.823

SOLUTION_SPECIES
    Tce = Tce
        log_k 0.0
        -gamma 1.0 0.0

    Ct = Ct
        log_k 0.0
        -gamma 1.0 0.0

PHASES
    TCE(g)
        Tce = Tce
        -log_k   -2.322559

    CCl4(g)
        Ct = Ct
        -log_k   -2.391164

END
"""

        # Load VOC definitions into PHREEQC
        pp.ip.run_string(voc_definitions)

        return pp

    def test_tce_henry_constant_with_co2(self, pp):
        """
        Test gas-liquid equilibrium with built-in CO2(g).

        This validates that phreeqpython gas phase equilibrium works
        before we test custom VOC phases.

        Expected behavior:
        - Pure water equilibrated with CO2(g) at 0.001 atm should acidify
        - pH should drop from ~7 to ~5.5-6.0 due to carbonic acid formation
        - Validates that pp.add_gas() and sol.interact() work correctly
        """
        # Create pure water solution
        sol = pp.add_solution({})
        initial_pH = sol.pH

        # Create CO2 gas phase at low partial pressure (1000 ppm in air)
        gas_co2 = pp.add_gas(
            components={'CO2(g)': 0.001},  # 0.001 atm = 1000 ppm
            volume=1.0,
            fixed_pressure=False,
            fixed_volume=True
        )

        # Equilibrate solution with gas phase
        sol.interact(gas_co2)

        # Verify pH dropped due to CO2 dissolution
        assert sol.pH < initial_pH, f"pH should drop after CO2 equilibration"
        assert 5.0 < sol.pH < 6.5, f"pH = {sol.pH:.2f}, expected 5.0-6.5 for CO2-equilibrated water"

        print(f"\nCO2 gas phase equilibrium test: PASSED")
        print(f"  Initial pH: {initial_pH:.2f}")
        print(f"  Final pH after CO2 equilibration: {sol.pH:.2f}")
        print(f"  CO2(g) partial pressure: {gas_co2.partial_pressures.get('CO2(g)', 0):.6f} atm")

    def test_tce_with_custom_phases(self, pp_with_voc):
        """
        Test TCE gas-liquid equilibrium with custom VOC phases.

        Test strategy:
        1. Start with pure water (no TCE)
        2. Equilibrate with TCE(g) at fixed pressure (0.001 atm)
        3. Verify aqueous TCE matches Henry's law prediction

        Expected behavior with H_dimensionless = 8.59:
        - At P_gas = 0.001 atm (1000 ppm in headspace):
          C_aq = P / (H * R * T) = 0.001 / (8.59 * 0.08206 * 298.15)
               = 4.76e-6 mol/L = 4.76 µM
        """
        # Expected Henry's constant for TCE
        H_dimensionless = 8.59  # Cgas/Caq at 25°C
        R_atm = 0.08206  # L·atm/(mol·K)
        T_ref = 298.15  # K (25°C)
        P_gas = 0.001  # atm (1000 ppm)

        # Calculate expected aqueous concentration at equilibrium
        C_expected_molL = P_gas / (H_dimensionless * R_atm * T_ref)
        C_expected_uM = C_expected_molL * 1e6

        # Create pure water solution (no TCE initially)
        sol = pp_with_voc.add_solution({
            'pH': 7.0,
            'temp': 25
        })

        # Create TCE gas phase at fixed pressure
        # IMPORTANT: Must specify pressure parameter explicitly when using fixed_pressure=True
        # Otherwise PHREEQC defaults to 1 atm (per Codex investigation)
        gas_tce = pp_with_voc.add_gas(
            components={'TCE(g)': P_gas},
            pressure=P_gas,  # Explicitly set total pressure to match component partial pressure
            volume=1.0,
            fixed_pressure=True,
            fixed_volume=False
        )

        # Equilibrate solution with gas phase
        sol.interact(gas_tce)

        # Get equilibrium concentrations
        C_aq_molL = sol.total('Tce', units='mol')
        C_aq_uM = C_aq_molL * 1e6
        P_eq = gas_tce.partial_pressures.get('TCE(g)', 0)

        print(f"\nTCE gas phase equilibrium test:")
        print(f"  Expected P_TCE: {P_gas} atm (input)")
        print(f"  Equilibrium P_TCE: {P_eq:.6f} atm")
        print(f"  Expected C_aq: {C_expected_uM:.2f} µM")
        print(f"  Measured C_aq: {C_aq_uM:.2f} µM")
        print(f"  Ratio C_measured/C_expected: {C_aq_uM/C_expected_uM if C_expected_uM > 0 else 0:.2f}")

        # The issue: P_eq appears to be normalized to 1.0 for single-component gas
        # Calculate what the actual pressure should be based on measured concentration
        if C_aq_molL > 0:
            K_expected = 1.0 / (H_dimensionless * R_atm * T_ref)  # mol/(L·atm)
            P_actual = C_aq_molL / K_expected
            print(f"  Actual P from C_aq: {P_actual:.6f} atm")
            print(f"  K_expected: {K_expected:.6f} mol/(L·atm)")
            K_measured = C_aq_molL / P_gas  # Use input pressure, not reported pressure
            print(f"  K_measured: {K_measured:.6f} mol/(L·atm)")
            print(f"  Ratio K_measured/K_expected: {K_measured/K_expected:.2f}")

        # Verify equilibrium matches Henry's law (within factor of 2)
        # Note: Some deviation expected due to PHREEQC numerical precision
        assert C_aq_molL > 0, "TCE aqueous concentration should be positive"
        assert 0.5 < C_aq_uM/C_expected_uM < 2.0, \
            f"C_measured/C_expected = {C_aq_uM/C_expected_uM:.2f}, expected ~1 (within 2x)"

    def test_voc_phases_file_format(self):
        """
        Test that voc_phases.dat has correct PHREEQC format.

        Checks:
        1. File exists
        2. Has PHASES block
        3. TCE(g) definition present
        4. -log_k value is negative (correct sign)
        5. -analytic coefficients present
        """
        voc_phases_path = Path(__file__).parent.parent / "databases" / "voc_phases.dat"

        assert voc_phases_path.exists(), "voc_phases.dat not found"

        content = voc_phases_path.read_text(encoding='utf-8')

        # Check for PHASES block
        assert "PHASES" in content, "No PHASES block found"
        # Note: END is not in voc_phases.dat because it's meant to be inserted before
        # the END in phreeqc.dat

        # Check for TCE definition
        assert "TCE(g)" in content, "TCE(g) not defined"
        assert "C2HCl3 = C2HCl3" in content, "TCE reaction not found"

        # Check for -log_k with negative value (correct convention)
        assert "-log_k -2.3" in content, "-log_k value should be negative for TCE"

        # Check for -analytic coefficients
        assert "-analytic" in content, "Temperature dependence coefficients not found"

        # Extract -log_k value for TCE
        import re
        log_k_match = re.search(r'-log_k\s+([-\d.]+)', content)
        assert log_k_match, "Could not parse -log_k value"

        log_k_value = float(log_k_match.group(1))

        # For TCE with H = 8.59:
        # K = 1/(H * R * T) = 1/(8.59 * 0.08206 * 298.15) = 0.00476
        # log_k = log10(0.00476) = -2.322559
        expected_log_k = -2.322559

        assert abs(log_k_value - expected_log_k) < 0.01, \
            f"TCE log_k = {log_k_value}, expected ~{expected_log_k}"

        print(f"\nVOC phases file format validation: PASSED")
        print(f"  TCE -log_k: {log_k_value:.6f} (expected: {expected_log_k:.6f})")

    def test_henry_constant_calculation(self):
        """
        Test Henry's constant conversion math.

        Given:
        - H_dimensionless = 8.59 (Cgas/Caq) for TCE at 25°C
        - R = 0.08206 L·atm/(mol·K)
        - T = 298.15 K

        Calculate:
        - K = 1/(H * R * T) = equilibrium constant for PHREEQC
        - At P_gas = 0.001 atm (1000 ppm in air):
          C_aq = P / (H * R * T) = 0.001 / (8.59 * 0.08206 * 298.15)
                = 4.76e-6 mol/L = 4.76 µM
        """
        import math

        # TCE properties
        H_dimensionless = 8.59  # Cgas/Caq
        R_atm = 0.08206  # L·atm/(mol·K)
        T_ref = 298.15  # K (25°C)

        # Calculate PHREEQC equilibrium constant
        K = 1.0 / (H_dimensionless * R_atm * T_ref)
        log_k = math.log10(K)

        # Expected values
        expected_K = 0.00476
        expected_log_k = -2.322559

        assert abs(K - expected_K) < 0.00001, f"K = {K}, expected ~{expected_K}"
        assert abs(log_k - expected_log_k) < 0.01, \
            f"log_k = {log_k}, expected ~{expected_log_k}"

        # Test aqueous concentration at typical gas phase concentration
        P_gas_atm = 0.001  # 1000 ppm in air
        C_aq_molL = P_gas_atm / (H_dimensionless * R_atm * T_ref)
        C_aq_uM = C_aq_molL * 1e6  # Convert to µM

        print(f"\nHenry's constant calculation validation:")
        print(f"  H (dimensionless): {H_dimensionless}")
        print(f"  K (PHREEQC): {K:.6f} mol/(L·atm)")
        print(f"  log_k: {log_k:.6f}")
        print(f"  At P_gas = {P_gas_atm} atm:")
        print(f"    C_aq = {C_aq_uM:.2f} µM")

        # Sanity check: aqueous concentration should be low for volatile compounds
        assert C_aq_uM < 10, "TCE should have low aqueous solubility at low pressure"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
