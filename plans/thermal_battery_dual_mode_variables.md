# Implementing Separate Heating and Cooling Variables

This document provides a detailed implementation plan for adding separate heating and cooling power variables to the thermal_battery component as part of the dual-mode approach. This is a critical component of enabling simultaneous heating and cooling capabilities in the optimizer.

## 1. Decision Variable Structure

The current implementation uses a single `p_deferrable` variable for each thermal battery. For the dual-mode approach, we need to split this into separate heating and cooling variables, along with binary indicators for mode selection.

### 1.1. Changes to `_initialize_decision_variables()`

```python
def _initialize_decision_variables(self):
    """Initialize all decision variables for the optimization problem."""
    # ... (existing code)
    
    # Deferrable load variables
    num_def_loads = len(self.optim_conf.get("def_total_hours", []))
    if num_def_loads > 0:
        # Create traditional p_deferrable variables (for backward compatibility)
        p_deferrable = [
            cp.Variable(self.num_timesteps, name=f"p_deferrable{k}")
            for k in range(num_def_loads)
        ]
        self.vars["p_deferrable"] = p_deferrable
        
        # Create thermal binary variables for when needed
        p_def_bin = [
            cp.Variable(self.num_timesteps, boolean=True, name=f"p_def_bin{k}")
            for k in range(num_def_loads)
        ]
        self.vars["p_def_bin"] = p_def_bin
        
        p_def_bin2 = [
            cp.Variable(self.num_timesteps, boolean=True, name=f"p_def_bin2{k}")
            for k in range(num_def_loads)
        ]
        self.vars["p_def_bin2"] = p_def_bin2
        
        # Create dual-mode thermal variables when applicable
        for k in range(num_def_loads):
            if (
                "def_load_config" in self.optim_conf.keys()
                and len(self.optim_conf["def_load_config"]) > k
                and "thermal_battery" in self.optim_conf["def_load_config"][k]
            ):
                # Check if dual mode is enabled
                hc = self.optim_conf["def_load_config"][k]["thermal_battery"]
                dual_mode_enabled = hc.get("dual_mode_enabled", True)
                
                if dual_mode_enabled:
                    # Create heating power variable
                    p_heat = cp.Variable(self.num_timesteps, name=f"p_heat_{k}")
                    self.vars[f"p_heat_{k}"] = p_heat
                    
                    # Create cooling power variable
                    p_cool = cp.Variable(self.num_timesteps, name=f"p_cool_{k}")
                    self.vars[f"p_cool_{k}"] = p_cool
                    
                    # Create binary mode indicators
                    heat_active = cp.Variable(self.num_timesteps, boolean=True, name=f"heat_active_{k}")
                    self.vars[f"heat_active_{k}"] = heat_active
                    
                    cool_active = cp.Variable(self.num_timesteps, boolean=True, name=f"cool_active_{k}")
                    self.vars[f"cool_active_{k}"] = cool_active
                    
                    # Create linking constraint for backward compatibility
                    # Note: p_deferrable will represent net effect (heating - cooling)
                    self.constraints.append(p_deferrable[k] == p_heat - p_cool)
                    
                    # Create power limit constraints based on binary indicators
                    nominal_power = self.optim_conf["nominal_power_of_deferrable_loads"][k]
                    self.constraints.append(p_heat <= heat_active * nominal_power)
                    self.constraints.append(p_cool <= cool_active * nominal_power)
                    
                    # Ensure at most one mode is active at a time 
                    self.constraints.append(heat_active + cool_active <= 1)
    
    # ... (rest of existing code)
```

### 1.2. Variable Storage for Parameters

We also need to update the thermal parameter storage to handle dual-mode specific parameters:

```python
def _update_thermal_start_temps(self, optim_conf):
    """Update the initial temperature parameters for thermal loads."""
    # ... (existing code)
    
    # For thermal_battery loads
    for k, cfg in enumerate(optim_conf.get("def_load_config", [])):
        # ... (existing code for thermal_config)
        
        elif "thermal_battery" in cfg:
            hc = cfg["thermal_battery"]
            init_temp = float(hc.get("start_temperature", 20.0) or 20.0)
            dual_mode_enabled = hc.get("dual_mode_enabled", True)
            
            # For dual mode, we need parameters for both modes
            if dual_mode_enabled:
                self.param_thermal[k] = {
                    "type": "thermal_battery_dual",
                    "start_temp": cp.Parameter(
                        name=f"thermal_battery_start_temp_{k}", value=init_temp
                    ),
                    "outdoor_temp": cp.Parameter(n, name=f"thermal_battery_outdoor_temp_{k}"),
                    "min_temps": cp.Parameter(n, name=f"thermal_battery_min_temps_{k}"),
                    "max_temps": cp.Parameter(n, name=f"thermal_battery_max_temps_{k}"),
                    "thermal_losses": cp.Parameter(n, name=f"thermal_battery_losses_{k}"),
                    
                    # Separate demands for heating and cooling
                    "heating_demand": cp.Parameter(
                        n, name=f"thermal_battery_heating_demand_{k}"
                    ),
                    "cooling_demand": cp.Parameter(
                        n, name=f"thermal_battery_cooling_demand_{k}"
                    ),
                    "solar_gains": cp.Parameter(n, name=f"thermal_battery_solar_gains_{k}"),
                    
                    # Separate COPs for heating and cooling
                    "heat_cops": cp.Parameter(n, name=f"thermal_battery_heat_cops_{k}"),
                    "cool_cops": cp.Parameter(n, name=f"thermal_battery_cool_cops_{k}"),
                }
            else:
                # Existing single-mode parameters
                self.param_thermal[k] = {
                    "type": "thermal_battery",
                    "start_temp": cp.Parameter(
                        name=f"thermal_battery_start_temp_{k}", value=init_temp
                    ),
                    # ... (existing parameters)
                }
```

## 2. Variable Bounds and Constraints

### 2.1. Power Variable Bounds

```python
# For each heating/cooling variable, ensure it's non-negative
constraints.append(p_heat >= 0)
constraints.append(p_cool >= 0)

# If we're using semi-continuous operation for the thermal load
if self.optim_conf["treat_deferrable_load_as_semi_cont"][k]:
    nominal_power = self.optim_conf["nominal_power_of_deferrable_loads"][k]
    
    # Heating power constraints
    constraints.append(p_heat <= heat_active * nominal_power)
    constraints.append(heat_active <= p_heat / (nominal_power * 0.01))
    
    # Cooling power constraints
    constraints.append(p_cool <= cool_active * nominal_power)
    constraints.append(cool_active <= p_cool / (nominal_power * 0.01))
```

### 2.2. Mutually Exclusive Operation Constraints

```python
# Cannot heat and cool at the same time
constraints.append(heat_active + cool_active <= 1)
```

### 2.3. Backward Compatibility for `p_deferrable`

```python
# Link p_deferrable to heating and cooling powers
# Positive value means heating dominates, negative means cooling dominates
constraints.append(p_deferrable[k] == p_heat - p_cool)
```

## 3. Min Run Time and Cycling Protection

To prevent rapid switching between heating and cooling, we implement minimum run time and transition cooldown constraints:

```python
# Minimum runtime for each mode
min_runtime = hc.get("min_runtime", 2)  # Minimum runtime in timesteps
if min_runtime > 1:
    for t in range(1, required_len):
        for i in range(1, min(min_runtime, required_len - t)):
            # If mode activated at t, it must stay active for next i steps
            constraints.append(heat_active[t] - heat_active[t-1] <= heat_active[t+i])
            constraints.append(cool_active[t] - cool_active[t-1] <= cool_active[t+i])

# Cooldown period between mode transitions
cooldown = hc.get("transition_cooldown", 1)  # Cooldown period in timesteps
if cooldown > 0:
    for t in range(cooldown, required_len):
        # Sum of mode activation in the cooldown period
        heating_in_cooldown = sum(heat_active[t-i] for i in range(1, cooldown+1))
        cooling_in_cooldown = sum(cool_active[t-i] for i in range(1, cooldown+1))
        
        # Can't activate cooling if heating was recently active
        constraints.append(cool_active[t] + heating_in_cooldown <= 1)
        
        # Can't activate heating if cooling was recently active
        constraints.append(heat_active[t] + cooling_in_cooldown <= 1)
```

## 4. Variable Initialization for the Optimizer

```python
# For dual-mode thermal batteries, extract and pre-compute required data
if is_dual_mode_thermal:
    # Extract heating/cooling specific parameters
    heat_supply_temp = hc.get("heat_supply_temperature", 35.0)
    cool_supply_temp = hc.get("cool_supply_temperature", 12.0)
    heat_efficiency = hc.get("heat_carnot_efficiency", 0.4)
    cool_efficiency = hc.get("cool_carnot_efficiency", 0.45)
    
    # Pre-compute COPs for both modes
    heat_cop, cool_cop = calculate_cop_dual_mode(
        heat_supply_temperature=heat_supply_temp,
        cool_supply_temperature=cool_supply_temp,
        heat_carnot_efficiency=heat_efficiency,
        cool_carnot_efficiency=cool_efficiency,
        outdoor_temperature_forecast=outdoor_temp_arr
    )
    
    # Store in parameters for potential reuse in warm-starting
    params["heat_cops"].value = heat_cop
    params["cool_cops"].value = cool_cop
```

## 5. Creating the Optimization Problem

The overall optimization problem structure must account for the dual mode variables and specialized constraints:

```python
def perform_optimization(self, data_opt: pd.DataFrame) -> dict:
    """Perform detailed optimization with dual-mode thermal capabilities."""
    # ... (existing initialization)
    
    # Build objective function, now accounting for dual-mode thermal batteries
    objective = self._build_objective_function()
    
    # Create the problem
    problem = cp.Problem(objective, self.constraints)
    
    # Solve and extract results, now with specialized dual-mode results handling
    try:
        problem.solve(solver=cp.GLPK, verbose=False)
        
        # Build results dataframe with dual-mode variables included
        df_results = self._build_results_dataframe()
        
        # ... (rest of function)
    except Exception as e:
        # ... (error handling)
```

## 6. Memory Considerations

The dual-mode approach introduces additional decision variables, which can increase the memory requirements for large optimization horizons. When implementing this approach, consider:

1. Variable cleanup during object deletion
2. Parameter warm-starting to reduce solve times
3. Careful tracking of initialized variables

## 7. Performance Optimization

To maintain good performance with the additional variables:

1. Consider adding a configuration option to disable dual-mode for performance-critical applications
2. Use sparse constraint matrix representations when possible
3. Implement warm-starting when solving sequential MPC problems
4. Add debug logging to track variable counts and memory usage

## 8. Code Organization

The variable implementation should be organized to:

1. Keep related variables together (heating power, cooling power, and mode indicators)
2. Use consistent naming patterns
3. Group constraints by logical function (power limits, mode selection, anti-cycling)
4. Maintain clear documentation of variable purposes and relationships