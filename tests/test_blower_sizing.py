"""
Tests for Blower Sizing and Pressure Drop Calculations

Validates Robbins correlation, blower power calculations, and integration
with heuristic sizing tool against Perry's Handbook examples and EPA case studies.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from utils.pressure_drop import (
    calculate_robbins_pressure_drop,
    calculate_total_system_pressure_drop
)
from utils.blower_sizing import (
    select_blower_type,
    calculate_isothermal_power,
    calculate_polytropic_power,
    calculate_blower_power
)
from tools.heuristic_sizing import heuristic_sizing


class TestRobbinsPressureDrop:
    """Test Robbins correlation against Perry's Handbook Example 13"""

    def test_perrys_example_13_2inch_pall_rings(self):
        """
        Perry's Handbook Example 13 (8th Ed, Section 14):
        2-inch metal Pall rings, air-water system

        Given:
        - Gas mass velocity: 2.03 kg/(s·m²) = 1500 lb/(hr·ft²)
        - Liquid mass velocity: 12.20 kg/(s·m²) = 9000 lb/(hr·ft²)
        - Packing factor: 27 ft⁻¹ = 88.6 m⁻¹
        - Gas density: 0.074 lb/ft³ = 1.186 kg/m³
        - Liquid density: 62.4 lb/ft³ = 1000 kg/m³
        - Liquid viscosity: 1.0 cP

        Expected:
        - Pressure drop: ~0.4-0.6 inches H₂O per foot of packing
        """
        # Perry's Example 13 conditions
        result = calculate_robbins_pressure_drop(
            packing_height_m=1.0,  # 1 meter for per-meter calculation
            tower_diameter_m=1.0,  # Not used in Robbins correlation
            gas_mass_velocity_kg_s_m2=2.03,
            liquid_mass_velocity_kg_s_m2=12.20,
            packing_factor_dry_m_inv=88.6,  # 27 ft⁻¹
            gas_density_kg_m3=1.186,
            liquid_density_kg_m3=1000.0,
            liquid_viscosity_cp=1.0
        )

        # Convert to inches H₂O per foot for comparison
        pressure_drop_inches_h2o_per_ft = result['total_pressure_drop_pa_m'] * 0.3048 / 249.089

        # Perry's example shows ~0.5 inches H₂O per foot
        # Allow ±20% tolerance due to correlation approximations
        assert 0.4 <= pressure_drop_inches_h2o_per_ft <= 0.7, \
            f"Pressure drop {pressure_drop_inches_h2o_per_ft:.3f} in H₂O/ft outside expected range"

        # Verify pressure drop is reasonable
        assert result['total_pressure_drop_pa_m'] > 0, "Pressure drop should be positive"
        assert result['total_pressure_drop_pa'] > 0, "Total pressure drop should be positive"

    def test_low_pressure_application(self):
        """Test pressure drop for typical air stripping (low pressure)"""
        # Typical H2S stripping conditions
        result = calculate_total_system_pressure_drop(
            packing_height_m=4.0,
            tower_height_m=5.0,
            tower_diameter_m=1.0,
            gas_flow_rate_m3_h=2000.0,
            liquid_flow_rate_m3_h=60.0,
            packing_factor_dry_m_inv=120.0,  # 50mm Pall rings
            gas_density_kg_m3=1.2,
            liquid_density_kg_m3=1000.0,
            liquid_viscosity_cp=1.0
        )

        # Total pressure drop should be < 2 psig for typical air stripping
        assert result['total_system_pressure_drop_psig'] < 2.0, \
            f"Pressure drop {result['total_system_pressure_drop_psig']:.2f} psig too high"

        # Packed bed should be dominant component
        assert result['packed_bed_pressure_drop_pa'] > result['demister_pressure_drop_pa'], \
            "Packed bed should dominate pressure drop"

        # Safety factor should be applied
        assert result['safety_factor_pa'] > 0, "Safety factor not applied"


class TestBlowerSelection:
    """Test automatic blower type selection"""

    def test_low_pressure_centrifugal(self):
        """Test selection of centrifugal blower for low pressure (β ≤ 1.2)"""
        selection = select_blower_type(compression_ratio=1.15)

        assert selection['blower_type'] == 'Multistage Centrifugal'
        assert selection['thermodynamic_model'] == 'Isothermal'
        assert 0.65 <= selection['default_efficiency'] <= 0.80

    def test_medium_pressure_rotary_lobe(self):
        """Test selection of rotary lobe for medium pressure (1.2 < β ≤ 1.5)"""
        selection = select_blower_type(compression_ratio=1.35)

        assert selection['blower_type'] == 'Rotary Lobe (Roots)'
        assert selection['thermodynamic_model'] == 'Polytropic'
        assert 0.60 <= selection['default_efficiency'] <= 0.70

    def test_high_pressure_compressor(self):
        """Test selection of compressor for high pressure (β > 1.5)"""
        selection = select_blower_type(compression_ratio=1.8)

        assert selection['blower_type'] == 'Single-Stage Compressor'
        assert selection['thermodynamic_model'] == 'Adiabatic'
        assert 0.70 <= selection['default_efficiency'] <= 0.85


class TestBlowerPower:
    """Test blower power calculations"""

    def test_isothermal_power_calculation(self):
        """Test isothermal power for low compression ratio"""
        # Typical air stripping: 2000 m³/h, 3 psig (20.7 kPa ΔP)
        volumetric_flow_m3_s = 2000.0 / 3600.0
        inlet_pressure_pa = 101325.0
        discharge_pressure_pa = 101325.0 + 20700.0  # +3 psig
        inlet_temperature_k = 298.15

        power_kw = calculate_isothermal_power(
            volumetric_flow_m3_s=volumetric_flow_m3_s,
            inlet_pressure_pa=inlet_pressure_pa,
            discharge_pressure_pa=discharge_pressure_pa,
            inlet_temperature_k=inlet_temperature_k,
            blower_efficiency=0.70
        )

        # Power should be in reasonable range for this duty
        # Rough check: W ≈ P·Q·ln(β)/η ≈ 101325·0.556·ln(1.204)/0.70 ≈ 15 kW
        assert 10.0 < power_kw < 25.0, f"Power {power_kw:.1f} kW outside expected range"

    def test_polytropic_power_calculation(self):
        """Test polytropic power for medium compression ratio"""
        volumetric_flow_m3_s = 2000.0 / 3600.0
        inlet_pressure_pa = 101325.0
        discharge_pressure_pa = 101325.0 + 34500.0  # +5 psig (β ≈ 1.34)
        inlet_temperature_k = 298.15

        result = calculate_polytropic_power(
            volumetric_flow_m3_s=volumetric_flow_m3_s,
            inlet_pressure_pa=inlet_pressure_pa,
            discharge_pressure_pa=discharge_pressure_pa,
            inlet_temperature_k=inlet_temperature_k,
            polytropic_efficiency=0.65
        )

        power_kw = result['shaft_power_kw']
        discharge_temperature_c = result['discharge_temperature_c']

        # Polytropic power should be higher than isothermal for same ΔP
        isothermal_kw = calculate_isothermal_power(
            volumetric_flow_m3_s, inlet_pressure_pa, discharge_pressure_pa, inlet_temperature_k, 0.65
        )

        assert power_kw > isothermal_kw, "Polytropic power should exceed isothermal"
        assert 15.0 < power_kw < 35.0, f"Power {power_kw:.1f} kW outside expected range"

        # Check discharge temperature is reasonable (should be warmer than inlet)
        # For β ≈ 1.34 with η_p=0.65, expect ~60-70°C rise (polytropic exponent n≈1.78)
        # Discharge temperature should be 80-95°C (much higher than old buggy calculation)
        assert 75.0 < discharge_temperature_c < 95.0, \
            f"Discharge temperature {discharge_temperature_c:.1f}°C outside expected range"

        # Temperature rise should be significant for polytropic compression
        temperature_rise = discharge_temperature_c - (inlet_temperature_k - 273.15)
        assert 50.0 < temperature_rise < 75.0, \
            f"Temperature rise {temperature_rise:.1f}°C outside expected range"

    def test_motor_power_includes_motor_efficiency(self):
        """Test that motor power accounts for motor efficiency"""
        result = calculate_blower_power(
            air_flow_rate_m3_h=2000.0,
            total_pressure_drop_pa=20000.0,
            motor_efficiency=0.92
        )

        # Motor power should be shaft power / motor efficiency
        expected_motor_power = result['shaft_power_kw'] / 0.92
        assert abs(result['motor_power_kw'] - expected_motor_power) < 0.01, \
            "Motor power calculation incorrect"


class TestIntegratedBlowerSizing:
    """Test integration with heuristic sizing tool"""

    @pytest.mark.asyncio
    async def test_h2s_stripping_with_blower(self):
        """
        Test H2S stripping case with blower sizing
        Based on previous H2S design at pH 6.0
        """
        result = await heuristic_sizing(
            application="H2S",
            water_flow_rate_m3_h=60.0,
            inlet_concentration_mg_L=32.0,
            outlet_concentration_mg_L=0.05,
            air_water_ratio=34.0,
            temperature_c=25.0,
            packing_id="Plastic_Pall_Rings_25mm",
            water_ph=6.0,
            include_blower_sizing=True,
            motor_efficiency=0.92
        )

        # Check that blower specs are included
        assert 'blower_specs' in result
        assert result['blower_specs'] is not None

        blower = result['blower_specs']

        # Check blower type selection (should be centrifugal for low pressure)
        assert blower['blower_type'] in ['Multistage Centrifugal', 'Rotary Lobe (Roots)']

        # Check compression ratio is reasonable (< 1.3 for air stripping)
        assert 1.0 < blower['compression_ratio'] < 1.3, \
            f"Compression ratio {blower['compression_ratio']:.3f} outside expected range"

        # Check motor power is reasonable for this duty (< 15 hp expected)
        assert 1.0 < blower['motor_power_hp'] < 20.0, \
            f"Motor power {blower['motor_power_hp']:.1f} hp outside expected range"

        # Check discharge pressure is reasonable
        assert 0.1 < blower['discharge_pressure_psig'] < 5.0, \
            f"Discharge pressure {blower['discharge_pressure_psig']:.2f} psig outside expected range"

        # Check pressure drop components
        assert blower['packed_bed_pressure_drop_pa'] > 0
        assert blower['inlet_distributor_pressure_drop_pa'] > 0
        assert blower['safety_factor_pa'] > 0

        # Total should equal sum of components
        total_calculated = (
            blower['packed_bed_pressure_drop_pa'] +
            blower['inlet_distributor_pressure_drop_pa'] +
            blower['outlet_distributor_pressure_drop_pa'] +
            blower['demister_pressure_drop_pa'] +
            blower['momentum_losses_pa'] +
            blower['ductwork_silencer_pressure_drop_pa'] +
            blower['elevation_head_pa'] +
            blower['safety_factor_pa']
        )

        assert abs(total_calculated - blower['total_system_pressure_drop_pa']) < 1.0, \
            "Pressure drop components don't sum to total"

    @pytest.mark.asyncio
    async def test_blower_sizing_optional(self):
        """Test that blower sizing can be disabled"""
        result = await heuristic_sizing(
            application="VOC",
            water_flow_rate_m3_h=100.0,
            inlet_concentration_mg_L=38.0,
            outlet_concentration_mg_L=0.00151,
            air_water_ratio=30.0,
            henry_constant_25C=8.59,
            include_blower_sizing=False
        )

        # Blower specs should be None
        assert result.get('blower_specs') is None

    @pytest.mark.asyncio
    async def test_blower_efficiency_override(self):
        """Test that blower efficiency can be overridden"""
        result = await heuristic_sizing(
            application="VOC",
            water_flow_rate_m3_h=100.0,
            inlet_concentration_mg_L=38.0,
            outlet_concentration_mg_L=0.00151,
            air_water_ratio=30.0,
            henry_constant_25C=8.59,
            include_blower_sizing=True,
            blower_efficiency_override=0.75,
            motor_efficiency=0.95
        )

        blower = result['blower_specs']

        # Check that overrides were applied
        assert blower['blower_efficiency'] == 0.75
        assert blower['motor_efficiency'] == 0.95


class TestPressureDropComponents:
    """Test individual pressure drop components"""

    def test_all_components_present(self):
        """Verify all 7 pressure drop components are calculated"""
        result = calculate_total_system_pressure_drop(
            packing_height_m=5.0,
            tower_height_m=6.0,
            tower_diameter_m=1.2,
            gas_flow_rate_m3_h=2000.0,
            liquid_flow_rate_m3_h=60.0,
            packing_factor_dry_m_inv=120.0
        )

        # Check all required keys are present
        required_keys = [
            'packed_bed_pressure_drop_pa',
            'inlet_distributor_pressure_drop_pa',
            'outlet_distributor_pressure_drop_pa',
            'demister_pressure_drop_pa',
            'momentum_losses_pa',
            'ductwork_silencer_pressure_drop_pa',
            'elevation_head_pa',
            'safety_factor_pa',
            'total_system_pressure_drop_pa'
        ]

        for key in required_keys:
            assert key in result, f"Missing component: {key}"
            assert result[key] > 0, f"Component {key} should be > 0"

    def test_safety_factor_percentage(self):
        """Test that safety factor is correctly applied as percentage"""
        result = calculate_total_system_pressure_drop(
            packing_height_m=5.0,
            tower_height_m=6.0,
            tower_diameter_m=1.2,
            gas_flow_rate_m3_h=2000.0,
            liquid_flow_rate_m3_h=60.0,
            packing_factor_dry_m_inv=120.0,
            safety_factor=0.15  # 15% safety factor
        )

        # Calculate total before safety
        total_before_safety = (
            result['packed_bed_pressure_drop_pa'] +
            result['inlet_distributor_pressure_drop_pa'] +
            result['outlet_distributor_pressure_drop_pa'] +
            result['demister_pressure_drop_pa'] +
            result['momentum_losses_pa'] +
            result['ductwork_silencer_pressure_drop_pa'] +
            result['elevation_head_pa']
        )

        # Safety factor should be 15% of total before safety
        expected_safety = 0.15 * total_before_safety
        assert abs(result['safety_factor_pa'] - expected_safety) / expected_safety < 0.01, \
            "Safety factor not correctly calculated"

        # Total should be (1 + 0.15) × total_before_safety
        expected_total = total_before_safety + expected_safety
        assert abs(result['total_system_pressure_drop_pa'] - expected_total) < 1.0, \
            "Total pressure drop incorrect"


@pytest.mark.asyncio
async def test_validation_against_fluids_library():
    """
    Regression test against fluids library (if available)

    This test validates that our Robbins implementation matches
    the CalebBell/fluids library implementation within tolerance.
    """
    try:
        from fluids.packed_tower import Robbins as fluids_robbins

        # Test case matching Perry's Example 13
        # fluids library expects SI units: kg/s/m², kg/m³, Pa·s, m, ft⁻¹
        L = 12.20  # kg/(s·m²)
        G = 2.03   # kg/(s·m²)
        rhol = 1000.0  # kg/m³
        rhog = 1.186   # kg/m³
        mul = 0.001    # Pa·s (1 cP)
        H = 1.0        # m
        Fpd = 27.0     # ft⁻¹

        # Calculate with fluids library (returns Pa)
        dP_fluids_pa = fluids_robbins(L=L, G=G, rhol=rhol, rhog=rhog, mul=mul, H=H, Fpd=Fpd)

        # Calculate with our implementation (also returns Pa)
        our_result = calculate_robbins_pressure_drop(
            packing_height_m=H,
            tower_diameter_m=1.0,  # Not used in Robbins
            gas_mass_velocity_kg_s_m2=G,
            liquid_mass_velocity_kg_s_m2=L,
            packing_factor_dry_m_inv=88.6,  # 27 ft⁻¹ × 1 m/3.2808 ft
            gas_density_kg_m3=rhog,
            liquid_density_kg_m3=rhol,
            liquid_viscosity_cp=1.0
        )

        dP_ours_pa = our_result['total_pressure_drop_pa']

        # Should match exactly (we're using fluids library internally now)
        relative_error = abs(dP_ours_pa - dP_fluids_pa) / dP_fluids_pa
        assert relative_error < 0.01, \
            f"Deviation from fluids library: {relative_error*100:.1f}% (ours: {dP_ours_pa:.1f} Pa, fluids: {dP_fluids_pa:.1f} Pa)"

    except ImportError:
        pytest.skip("fluids library not available for validation")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
