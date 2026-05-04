# Anti-Cycling Protection for Dual-Mode Thermal Battery

This document details the implementation of anti-cycling protection mechanisms for the dual-mode thermal battery component. These mechanisms prevent rapid switching between heating and cooling modes, which can cause equipment wear and reduce system efficiency.

## 1. Understanding Anti-Cycling Requirements

### 1.1. The Problem of Cycling

Heat pumps and HVAC systems in general are designed to operate efficiently with relatively long run times. Frequent switching between on and off states, or between heating and cooling modes, can lead to several issues:

1. **Equipment Wear**: Compressors and valves experience mechanical stress during mode changes
2. **Energy Inefficiency**: Mode switching often requires energy-intensive startup procedures
3. **Thermal Inefficiency**: Systems operate at peak efficiency once they reach steady-state
4. **Reduced Lifespan**: Frequent cycling can significantly reduce equipment service life
5. **Comfort Issues**: Mode switching can cause temperature fluctuations

### 1.2. Types of Cycling Protection Needed

For a dual-mode thermal battery, we need to implement several types of protection:

1. **Minimum Run Time**: Once a mode (heating or cooling) is activated, it should remain active for a minimum duration
2. **Mode Transition Cooldown**: After switching between modes, a cooldown period should be enforced
3. **Switching Frequency Limitation**: Limit the total number of mode changes within the optimization horizon

## 2. Configuration Parameters

The anti-cycling protection will be controlled by three main configuration parameters:

```json
"thermal_battery": {
  // Other parameters...
  "min_runtime": 2,             // Minimum runtime in timesteps (default: 2)
  "transition_cooldown": 1,     // Cooldown between mode switches in timesteps (default: 1)
  "max_mode_switches": 6,       // Maximum number of mode switches in horizon (default: 6)
}
```

## 3. Implementation in CVXPY

### 3.1. Minimum Runtime Constraints

Once a mode is activated, it should remain active for at least `min_runtime` consecutive timesteps:

```python
# Minimum runtime constraints
min_runtime = hc.get("min_runtime", 2)
if min_runtime > 1:
    for t in range(1, required_len):
        # For heating mode: If activated at t (but wasn't active at t-1), 
        # must remain active for min_runtime steps (or until end of horizon)
        for i in range(1, min(min_runtime, required_len - t)):
            constraints.append(
                heat_active[t] - heat_active[t-1] <= heat_active[t + i]
            )
        
        # For cooling mode: Similar constraint
        for i in range(1, min(min_runtime, required_len - t)):
            constraints.append(
                cool_active[t] - cool_active[t-1] <= cool_active[t + i]
            )
```

The constraint `heat_active[t] - heat_active[t-1] <= heat_active[t + i]` works as follows:
- If mode was already active at t-1, then the difference is 0 or negative, making the constraint trivially satisfied
- If mode was activated at t, then the difference is 1, forcing `heat_active[t + i]` to be 1 for the next i timesteps

### 3.2. Mode Transition Cooldown

After switching from one mode to the other, enforce a cooldown period:

```python
# Mode transition cooldown constraints
transition_cooldown = hc.get("transition_cooldown", 1)
if transition_cooldown > 0:
    for t in range(transition_cooldown, required_len):
        # Can't activate heating if cooling was active in the cooldown period
        for i in range(1, transition_cooldown + 1):
            constraints.append(
                heat_active[t] + cool_active[t-i] <= 1
            )
        
        # Can't activate cooling if heating was active in the cooldown period
        for i in range(1, transition_cooldown + 1):
            constraints.append(
                cool_active[t] + heat_active[t-i] <= 1
            )
```

This prevents activating one mode if the other mode was active during the cooldown period.

### 3.3. Switching Frequency Limitation

To limit the total number of mode switches in the optimization horizon:

```python
# Limit total number of mode switches
max_mode_switches = hc.get("max_mode_switches", 6)

# Create binary variables to track mode changes
heat_activated = cp.Variable(required_len, boolean=True, name=f"heat_activated_{k}")
cool_activated = cp.Variable(required_len, boolean=True, name=f"cool_activated_{k}")

# Heat activated when it wasn't active in the previous timestep
for t in range(1, required_len):
    constraints.append(heat_activated[t] >= heat_active[t] - heat_active[t-1])
    constraints.append(heat_activated[t] <= 1 - heat_active[t-1])
    constraints.append(heat_activated[t] <= heat_active[t])

# Cool activated when it wasn't active in the previous timestep
for t in range(1, required_len):
    constraints.append(cool_activated[t] >= cool_active[t] - cool_active[t-1])
    constraints.append(cool_activated[t] <= 1 - cool_active[t-1])
    constraints.append(cool_activated[t] <= cool_active[t])

# First timestep special case
constraints.append(heat_activated[0] == heat_active[0])
constraints.append(cool_activated[0] == cool_active[0])

# Limit total mode activations
constraints.append(cp.sum(heat_activated) + cp.sum(cool_activated) <= max_mode_switches)
```

This tracks each instance where a mode is activated and limits the total number of activations.

### 3.4. Combined Implementation

Here's a complete implementation of all anti-cycling constraints:

```python
def _add_anti_cycling_constraints(self, constraints, k, heat_active, cool_active, required_len):
    """
    Add anti-cycling protection constraints to prevent frequent mode switching.
    
    :param constraints: List to add constraints to
    :param k: Deferrable load index
    :param heat_active: Binary variable array for heating mode activation
    :param cool_active: Binary variable array for cooling mode activation
    :param required_len: Length of the optimization horizon
    """
    # Get configuration
    hc = self.optim_conf["def_load_config"][k]["thermal_battery"]
    min_runtime = hc.get("min_runtime", 2)
    transition_cooldown = hc.get("transition_cooldown", 1)
    max_mode_switches = hc.get("max_mode_switches", 6)
    
    # 1. Minimum runtime constraints
    if min_runtime > 1:
        for t in range(1, required_len):
            # Only apply if we have enough timesteps left
            max_future = min(min_runtime, required_len - t)
            
            # For each mode: if activated at t, must stay on for min_runtime
            for i in range(1, max_future):
                # Heating minimum runtime
                constraints.append(
                    heat_active[t] - heat_active[t-1] <= heat_active[t + i]
                )
                
                # Cooling minimum runtime
                constraints.append(
                    cool_active[t] - cool_active[t-1] <= cool_active[t + i]
                )
    
    # 2. Transition cooldown constraints
    if transition_cooldown > 0:
        for t in range(transition_cooldown, required_len):
            # Creating efficient sum for multiple timesteps
            heating_in_cooldown = sum(heat_active[t-i] for i in range(1, transition_cooldown+1))
            cooling_in_cooldown = sum(cool_active[t-i] for i in range(1, transition_cooldown+1))
            
            # Can't activate cooling if heating was recently active
            constraints.append(cool_active[t] * transition_cooldown + heating_in_cooldown <= transition_cooldown)
            
            # Can't activate heating if cooling was recently active
            constraints.append(heat_active[t] * transition_cooldown + cooling_in_cooldown <= transition_cooldown)
    
    # 3. Mode switching frequency limitation
    if max_mode_switches < required_len:
        # Create activation tracking variables
        heat_activated = cp.Variable(required_len, boolean=True, name=f"heat_activated_{k}")
        cool_activated = cp.Variable(required_len, boolean=True, name=f"cool_activated_{k}")
        
        # Store for later access if needed
        self.vars[f"heat_activated_{k}"] = heat_activated
        self.vars[f"cool_activated_{k}"] = cool_activated
        
        # First timestep is special case (activated if mode is on)
        constraints.append(heat_activated[0] == heat_active[0])
        constraints.append(cool_activated[0] == cool_active[0])
        
        # For remaining timesteps, activation happens when on but wasn't on before
        for t in range(1, required_len):
            # Heater activation logic
            constraints.append(heat_activated[t] >= heat_active[t] - heat_active[t-1])
            constraints.append(heat_activated[t] <= heat_active[t])
            constraints.append(heat_activated[t] <= 1 - heat_active[t-1])
            
            # Cooler activation logic
            constraints.append(cool_activated[t] >= cool_active[t] - cool_active[t-1])
            constraints.append(cool_activated[t] <= cool_active[t])
            constraints.append(cool_activated[t] <= 1 - cool_active[t-1])
        
        # Limit total activations
        constraints.append(cp.sum(heat_activated) + cp.sum(cool_activated) <= max_mode_switches)
```

## 4. Smart Constraint Generation

The anti-cycling constraints can increase problem complexity significantly. To improve performance, we can implement smart constraint generation:

1. Only apply constraints when necessary (based on configuration)
2. Use more efficient formulations when possible
3. Handle edge cases appropriately

### 4.1. Performance Optimizations

```python
# More efficient minimum runtime constraint for longer durations
if min_runtime > 4:
    # Uses a cumulative approach for consecutive binary variables
    for t in range(1, required_len - min_runtime + 1):
        # Sum of consecutive timesteps must be either 0 or min_runtime or more
        heat_run_sum = cp.sum(heat_active[t:t+min_runtime])
        constraints.append(
            heat_run_sum >= min_runtime * (heat_active[t] - heat_active[t-1])
        )
        
        cool_run_sum = cp.sum(cool_active[t:t+min_runtime])
        constraints.append(
            cool_run_sum >= min_runtime * (cool_active[t] - cool_active[t-1])
        )
```

This alternate formulation can be more efficient for longer minimum runtimes as it creates fewer constraints.

### 4.2. Handling Short Horizons

For short horizons, we need to adjust the constraints to prevent infeasibility:

```python
# Adjust parameters for short horizons
if required_len < 6:
    min_runtime = min(min_runtime, max(1, required_len // 3))
    transition_cooldown = min(transition_cooldown, max(0, (required_len - 2) // 2))
    max_mode_switches = min(max_mode_switches, required_len)
```

## 5. Interaction with Objective Function

The anti-cycling constraints may create a tension with the optimization objective. In some cases, the most cost-effective solution might involve frequent mode switching. To further discourage cycling, we can add a mode-switching penalty to the objective function:

```python
# Add mode switching penalty to objective
switch_penalty = hc.get("switch_penalty", 0.1)  # kWh equivalent penalty
if switch_penalty > 0:
    # Create switching variables if not already created
    if f"heat_activated_{k}" not in self.vars:
        heat_activated = cp.Variable(required_len, boolean=True, name=f"heat_activated_{k}")
        cool_activated = cp.Variable(required_len, boolean=True, name=f"cool_activated_{k}")
        self.vars[f"heat_activated_{k}"] = heat_activated
        self.vars[f"cool_activated_{k}"] = cool_activated
        
        # Define activation logic
        # (Code as in previous section)
    
    # Add penalty to objective
    switching_cost = switch_penalty * (cp.sum(self.vars[f"heat_activated_{k}"]) + 
                                     cp.sum(self.vars[f"cool_activated_{k}"])) 
    objective += switching_cost
```

## 6. Testing and Validation

The anti-cycling constraints should be tested in various scenarios:

1. **Short Horizon Tests**: Verify proper behavior with few timesteps
2. **Long Horizon Tests**: Check performance with many timesteps
3. **Edge Cases**: Test with extreme parameter values
4. **Realistic Scenarios**: Test with typical weather and price patterns

### 6.1. Expected Behavior

When properly implemented, the anti-cycling protection should:

1. Prevent rapid oscillation between heating and cooling
2. Maintain minimum run times for each mode
3. Ensure adequate cooldown periods between mode switches
4. Limit the total number of mode changes in the optimization horizon
5. Not introduce unnecessary conservatism that prevents beneficial mode changes

## 7. Practical Considerations

### 7.1. Recommended Default Values

Based on typical HVAC equipment specifications:

| Parameter | Default | Min | Max | Notes |
|-----------|---------|-----|-----|-------|
| min_runtime | 2 | 1 | 8 | Timesteps (with 30-min timesteps, default is 1 hour) |
| transition_cooldown | 1 | 0 | 4 | Timesteps (with 30-min timesteps, default is 30 min) |
| max_mode_switches | 6 | 2 | 12 | For 24-hour horizon (default allows switching every 4 hours) |

### 7.2. Physical System Considerations

Real systems have inherent limitations on switching frequency due to:

1. **Compressor Protection**: Many heat pumps have built-in timers that prevent rapid cycling
2. **Valve Actuation**: Mode change requires physical movement of reversing valves
3. **Refrigerant Pressure Equalization**: Switching modes often requires pressure equalization

The constraints should reflect these physical realities while maintaining optimization flexibility.

## 8. Implementation Integration

The anti-cycling protection should be integrated into the `_add_thermal_battery_constraints` method:

```python
def _add_thermal_battery_constraints(self, constraints, k, data_opt, p_load):
    # ... (existing code)
    
    # Add anti-cycling protection if dual mode is enabled
    if dual_mode_enabled:
        self._add_anti_cycling_constraints(
            constraints, k, 
            self.vars[f"heat_active_{k}"], 
            self.vars[f"cool_active_{k}"],
            required_len
        )
    
    # ... (continuing with other constraints)