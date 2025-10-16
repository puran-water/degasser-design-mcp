"""
Pydantic Schemas for Heuristic Sizing Tool

Defines input and output models for the degasser heuristic sizing MCP tool.
Follows water-chemistry-mcp pattern with validation and documentation.

Reference:
- Perry's Chemical Engineers' Handbook 8th Ed, Section 14
- Eckert GPDC (Figures 14-55, 14-56)
- HTU/NTU method (Equations 14-15 to 14-22)
"""

from typing import Optional, Literal, List
from dataclasses import dataclass
from pydantic import BaseModel, Field, PositiveFloat, field_validator


class DesignWarning(BaseModel):
    """
    Structured warning for design limitations and recommendations.

    Allows programmatic handling of warnings (e.g., UI display, decision logic)
    instead of requiring log parsing.
    """

    severity: Literal["info", "warning", "critical"] = Field(
        description="Warning severity level"
    )

    category: Literal["ph_drift", "low_strippable_fraction", "flooding_risk", "pressure_drop", "general"] = Field(
        description="Warning category for filtering/routing"
    )

    message: str = Field(
        description="Human-readable warning message"
    )

    recommendations: List[str] = Field(
        description="Actionable recommendations to address the warning"
    )

    estimated_error_range: Optional[str] = Field(
        default=None,
        description="Estimated error range (e.g., '50-200% height underestimate')"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "severity": "critical",
                    "category": "ph_drift",
                    "message": "Operating at pH 7.8 without acid control. pH drift will reduce strippable fraction.",
                    "recommendations": [
                        "Acidify feed to pH 5.5-6.5 (reduces tower height 3-5×)",
                        "Use Tier 2 simulation tool for accurate pH-coupled sizing"
                    ],
                    "estimated_error_range": "50-200% height underestimate"
                }
            ]
        }
    }


class HeuristicSizingInput(BaseModel):
    """
    Input parameters for heuristic packed tower degasser sizing.

    All concentrations are mass-based (mg/L or ppm).
    Flow rates are volumetric.
    """

    application: Literal["CO2", "H2S", "VOC", "general"] = Field(
        description="Type of stripping application: CO2 (alkalinity removal), "
        "H2S (sulfide removal), VOC (volatile organic removal), or general"
    )

    water_flow_rate_m3_h: PositiveFloat = Field(
        description="Water flow rate in m³/h (cubic meters per hour)",
        examples=[100.0, 500.0, 1000.0]
    )

    inlet_concentration_mg_L: PositiveFloat = Field(
        description="Inlet contaminant concentration in mg/L (or ppm for dissolved gases)",
        examples=[38.0, 100.0, 5.0]
    )

    outlet_concentration_mg_L: PositiveFloat = Field(
        description="Target outlet contaminant concentration in mg/L (or ppm)",
        examples=[0.00151, 0.1, 0.05]
    )

    air_water_ratio: PositiveFloat = Field(
        default=30.0,
        description="Volumetric air-to-water ratio (dimensionless). "
        "Typical range: 20-50 for CO2/H2S, 30-100 for VOCs",
        examples=[30.0, 50.0, 80.0]
    )

    temperature_c: float = Field(
        default=25.0,
        ge=0.0,
        le=100.0,
        description="Operating temperature in degrees Celsius",
        examples=[15.0, 25.0, 35.0]
    )

    packing_id: Optional[str] = Field(
        default=None,
        description="Packing identifier from pack.json catalog "
        "(e.g., 'Metal_Pall_Rings_50mm', 'Plastic_Pall_Rings_50mm'). "
        "If None, uses application-specific default packing.",
        examples=["Metal_Pall_Rings_50mm", "Ceramic_Intalox_Saddles_25mm"]
    )

    henry_constant_25C: Optional[PositiveFloat] = Field(
        default=None,
        description="Dimensionless Henry's constant at 25°C (Cgas/Caq). "
        "If None, uses default for application. Override for custom compounds.",
        examples=[8.59, 0.3, 50.0]
    )

    water_ph: Optional[float] = Field(
        default=None,
        ge=4.0,
        le=10.0,
        description=(
            "Water pH for pH-dependent speciation calculation (H2S/CO2 only). "
            "Required for H2S and CO2 applications to account for HS⁻/HCO3⁻ non-strippable fractions. "
            "Ignored for VOC applications. "
            "\n\n⚠️  IMPORTANT: For pH ≥ 7.0, this heuristic assumes FIXED pH throughout the tower. "
            "Reality: pH drifts as CO₂ strips, reducing strippable fraction along tower height. "
            "This may underestimate tower height by 50-200% at neutral/alkaline pH. "
            "\n\nRECOMMENDATIONS: "
            "(1) For accurate heuristic sizing, acidify feed to pH 5.5-6.5, OR "
            "(2) Use Tier 2 simulation tool for pH-coupled analysis at neutral/alkaline pH."
        ),
        examples=[7.8, 8.5, 6.0]
    )

    @field_validator('outlet_concentration_mg_L')
    @classmethod
    def validate_outlet_less_than_inlet(cls, v, info):
        """Ensure outlet concentration is less than inlet."""
        if 'inlet_concentration_mg_L' in info.data:
            inlet = info.data['inlet_concentration_mg_L']
            if v >= inlet:
                raise ValueError(
                    f"outlet_concentration_mg_L ({v}) must be less than "
                    f"inlet_concentration_mg_L ({inlet})"
                )
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "application": "VOC",
                    "water_flow_rate_m3_h": 100.0,
                    "inlet_concentration_mg_L": 38.0,
                    "outlet_concentration_mg_L": 0.00151,
                    "air_water_ratio": 30.0,
                    "temperature_c": 25.0,
                    "packing_id": "Metal_Pall_Rings_50mm",
                    "henry_constant_25C": 8.59
                }
            ]
        }
    }


class HeuristicSizingResult(BaseModel):
    """
    Output from heuristic packed tower degasser sizing.

    Provides tower dimensions, packing specifications, and performance metrics.
    """

    # Tower Dimensions
    tower_diameter_m: float = Field(
        description="Tower diameter in meters (based on 70% of flooding velocity)",
        examples=[1.2, 2.5, 3.8]
    )

    tower_height_m: float = Field(
        description="Total tower height in meters (packing + disengagement space)",
        examples=[4.5, 8.2, 12.0]
    )

    packing_height_m: float = Field(
        description="Packed bed height in meters (includes safety factor)",
        examples=[4.0, 7.5, 11.0]
    )

    # Packing Specifications
    packing_id: str = Field(
        description="Packing identifier used in design",
        examples=["Metal_Pall_Rings_50mm"]
    )

    packing_name: str = Field(
        description="Human-readable packing name",
        examples=["Metal Pall Rings", "Plastic Pall Rings"]
    )

    packing_size_mm: float = Field(
        description="Nominal packing size in millimeters",
        examples=[25.0, 38.0, 50.0]
    )

    packing_factor_m_inv: float = Field(
        description="Packing factor Fp in m^-1 (used in flooding correlation)",
        examples=[121, 180, 220]
    )

    packing_surface_area_m2_m3: float = Field(
        description="Packing surface area per unit volume in m^2/m^3",
        examples=[102, 121, 206]
    )

    # Performance Metrics
    design_velocity_m_s: float = Field(
        description="Design gas velocity in m/s (70% of flooding)",
        examples=[1.5, 2.1, 3.2]
    )

    flooding_velocity_m_s: float = Field(
        description="Flooding velocity in m/s (from Eckert GPDC)",
        examples=[2.1, 3.0, 4.6]
    )

    ntu: float = Field(
        description="Number of transfer units NOG (dimensionless)",
        examples=[3.75, 5.2, 8.1]
    )

    htu_m: float = Field(
        description="Height of transfer unit HOG in meters (from Perry's Eq 14-158)",
        examples=[0.8, 1.2, 1.5]
    )

    lambda_factor: float = Field(
        description="Stripping factor lambda = H * (G/L) (dimensionless)",
        examples=[257.7, 50.0, 100.0]
    )

    # Flow Rates
    air_flow_rate_m3_h: float = Field(
        description="Air flow rate in m^3/h",
        examples=[3000.0, 5000.0, 8000.0]
    )

    water_flow_rate_m3_h: float = Field(
        description="Water flow rate in m^3/h (echoed from input)",
        examples=[100.0, 500.0, 1000.0]
    )

    air_water_ratio: float = Field(
        description="Volumetric air-to-water ratio (echoed from input)",
        examples=[30.0, 50.0, 80.0]
    )

    removal_efficiency_percent: float = Field(
        description="Contaminant removal efficiency in percent",
        examples=[99.99, 95.0, 99.5]
    )

    # Debug/Diagnostic Fields (optional)
    flow_parameter: Optional[float] = Field(
        default=None,
        description="GPDC flow parameter FLG = (L/G) * sqrt(rho_G/rho_L)",
        examples=[0.05, 0.1, 0.2]
    )

    capacity_parameter: Optional[float] = Field(
        default=None,
        description="GPDC capacity parameter at flooding (from Fig 14-55)",
        examples=[0.2, 0.28, 0.35]
    )

    # Blower Specifications (optional)
    blower_specs: Optional['BlowerSpecifications'] = Field(
        default=None,
        description="Blower sizing specifications including pressure drop and power consumption"
    )

    # Design Warnings (structured)
    warnings: List[DesignWarning] = Field(
        default=[],
        description="Structured warnings for design limitations (e.g., pH drift, low driving force)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tower_diameter_m": 2.5,
                    "tower_height_m": 4.5,
                    "packing_height_m": 4.0,
                    "packing_id": "Metal_Pall_Rings_50mm",
                    "packing_name": "Metal Pall Rings",
                    "packing_size_mm": 50.0,
                    "packing_factor_m_inv": 121,
                    "packing_surface_area_m2_m3": 121,
                    "design_velocity_m_s": 2.1,
                    "flooding_velocity_m_s": 3.0,
                    "ntu": 3.75,
                    "htu_m": 0.8,
                    "lambda_factor": 257.7,
                    "air_flow_rate_m3_h": 3000.0,
                    "water_flow_rate_m3_h": 100.0,
                    "air_water_ratio": 30.0,
                    "removal_efficiency_percent": 99.996
                }
            ]
        }
    }


class BlowerSpecifications(BaseModel):
    """
    Blower sizing and performance specifications.

    Includes pressure drop breakdown, blower selection, and power requirements.
    No OPEX calculations (delegated to separate economic analysis tool).
    """

    # Pressure Drop Breakdown
    packed_bed_pressure_drop_pa: float = Field(
        description="Packed bed pressure drop from Robbins correlation, Pa",
        examples=[1000.0, 2500.0, 5000.0]
    )

    inlet_distributor_pressure_drop_pa: float = Field(
        description="Inlet vapor distributor pressure drop, Pa",
        examples=[249.0, 373.0]
    )

    outlet_distributor_pressure_drop_pa: float = Field(
        description="Outlet vapor distributor pressure drop, Pa",
        examples=[249.0, 373.0]
    )

    demister_pressure_drop_pa: float = Field(
        description="Demister/coalescer pad pressure drop, Pa",
        examples=[373.0, 498.0]
    )

    momentum_losses_pa: float = Field(
        description="Entrance/exit momentum losses, Pa",
        examples=[50.0, 150.0]
    )

    ductwork_silencer_pressure_drop_pa: float = Field(
        description="Ductwork and silencer pressure drop, Pa",
        examples=[100.0, 500.0]
    )

    elevation_head_pa: float = Field(
        description="Tower elevation static head, Pa",
        examples=[50.0, 100.0]
    )

    safety_factor_pa: float = Field(
        description="Design safety factor pressure allowance, Pa",
        examples=[250.0, 500.0]
    )

    total_system_pressure_drop_pa: float = Field(
        description="Total system pressure drop (sum + safety factor), Pa",
        examples=[2500.0, 5000.0, 10000.0]
    )

    total_system_pressure_drop_inches_h2o: float = Field(
        description="Total system pressure drop in inches H₂O",
        examples=[10.0, 20.0, 40.0]
    )

    total_system_pressure_drop_psig: float = Field(
        description="Total system pressure drop in psig",
        examples=[0.36, 0.73, 1.45]
    )

    # Blower Selection
    blower_type: str = Field(
        description="Selected blower type based on compression ratio",
        examples=["Multistage Centrifugal", "Rotary Lobe (Roots)", "Single-Stage Compressor"]
    )

    compression_ratio: float = Field(
        description="Compression ratio β = P_discharge / P_inlet",
        examples=[1.05, 1.15, 1.30]
    )

    discharge_pressure_pa: float = Field(
        description="Blower discharge pressure, Pa absolute",
        examples=[103825.0, 106325.0, 111325.0]
    )

    discharge_pressure_psig: float = Field(
        description="Blower discharge pressure, psig gauge",
        examples=[0.36, 0.73, 1.45]
    )

    # Temperatures
    inlet_temperature_c: float = Field(
        description="Blower inlet temperature, °C",
        examples=[15.0, 25.0, 35.0]
    )

    discharge_temperature_c: float = Field(
        description="Blower discharge temperature, °C",
        examples=[25.0, 35.0, 50.0]
    )

    # Power & Efficiency
    thermodynamic_model: str = Field(
        description="Thermodynamic model used for power calculation",
        examples=["Isothermal", "Polytropic", "Adiabatic"]
    )

    shaft_power_kw: float = Field(
        description="Required shaft power, kW",
        examples=[5.0, 10.0, 25.0]
    )

    motor_power_kw: float = Field(
        description="Motor nameplate power, kW",
        examples=[5.5, 11.0, 30.0]
    )

    motor_power_hp: float = Field(
        description="Motor nameplate power, horsepower",
        examples=[7.5, 15.0, 40.0]
    )

    blower_efficiency: float = Field(
        description="Blower isentropic/polytropic efficiency (0-1)",
        examples=[0.65, 0.70, 0.75]
    )

    motor_efficiency: float = Field(
        description="Electric motor efficiency (0-1)",
        examples=[0.90, 0.92, 0.95]
    )

    # Optional: Aftercooling (for high compression ratios)
    aftercooling_heat_duty_kw: Optional[float] = Field(
        default=None,
        description="Aftercooling heat duty if required, kW",
        examples=[10.0, 25.0, 50.0]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "packed_bed_pressure_drop_pa": 1500.0,
                    "inlet_distributor_pressure_drop_pa": 249.0,
                    "outlet_distributor_pressure_drop_pa": 249.0,
                    "demister_pressure_drop_pa": 373.0,
                    "momentum_losses_pa": 75.0,
                    "ductwork_silencer_pressure_drop_pa": 150.0,
                    "elevation_head_pa": 60.0,
                    "safety_factor_pa": 318.0,
                    "total_system_pressure_drop_pa": 2974.0,
                    "total_system_pressure_drop_inches_h2o": 11.94,
                    "total_system_pressure_drop_psig": 0.43,
                    "blower_type": "Multistage Centrifugal",
                    "compression_ratio": 1.029,
                    "discharge_pressure_pa": 104299.0,
                    "discharge_pressure_psig": 0.43,
                    "inlet_temperature_c": 25.0,
                    "discharge_temperature_c": 25.5,
                    "thermodynamic_model": "Isothermal",
                    "shaft_power_kw": 8.5,
                    "motor_power_kw": 9.2,
                    "motor_power_hp": 12.4,
                    "blower_efficiency": 0.70,
                    "motor_efficiency": 0.92
                }
            ]
        }
    }


class PackingInfo(BaseModel):
    """Information about an available packing from the catalog."""

    packing_id: str = Field(description="Packing identifier")
    name: str = Field(description="Packing name")
    material: str = Field(description="Material (Metal, Plastic, Ceramic)")
    nominal_size_mm: float = Field(description="Nominal size in mm")
    nominal_size_in: float = Field(description="Nominal size in inches")
    packing_factor_m_inv: float = Field(description="Packing factor Fp in m^-1")
    surface_area_m2_m3: float = Field(description="Surface area in m^2/m^3")
    void_fraction: float = Field(description="Void fraction (0-1)")
    bed_density_kg_m3: float = Field(description="Bed density in kg/m^3")


class PackingCatalogResult(BaseModel):
    """Result from querying the packing catalog."""

    packings: list[PackingInfo] = Field(
        description="List of available packings"
    )

    count: int = Field(
        description="Number of packings returned"
    )


@dataclass
class Tier1Outcome:
    """
    Bundle of Tier 1 request and response for Tier 2 consumption.

    Following industrial flowsheeting pattern: rigorous models need both
    the original spec AND the heuristic result. This avoids brittle
    key lookups and makes the API self-documenting.

    Attributes:
        request: Original sizing input parameters
        result: Heuristic sizing output (tower dimensions, packing, etc.)
        henry_constant: Resolved Henry's constant (for Tier 2 convenience)
        molecular_weight: Contaminant molecular weight (for Tier 2 convenience)
        gas_phase_name: PHREEQC gas phase name (e.g., "TCE(g)", "H2S(g)")
    """
    request: HeuristicSizingInput
    result: HeuristicSizingResult
    henry_constant: float  # Resolved from defaults or override
    molecular_weight: float  # Application-specific MW
    gas_phase_name: str  # PHREEQC phase name for equilibrium_stage()
