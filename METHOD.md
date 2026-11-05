# Calculation method

## Scope and provenance

This implementation was rebuilt from the supplied project description. The
original optimization source and candidate formulation/scoring routines were
unavailable. This version reports a single global weighted nonnegative
least-squares solution and does not claim numerical equivalence to that original.

The six fertilizer choices follow the project's documented nutrient-control
context. They are explicit configurable assumptions, not inferred product labels.

## Units and ordering

| Position | Ionic species | Concentration basis |
| --- | --- | --- |
| 1 | NO3- | mg nitrate per L |
| 2 | K+ | mg potassium per L |
| 3 | Ca2+ | mg calcium per L |
| 4 | Mg2+ | mg magnesium per L |
| 5 | SO4(2-) | mg sulfate per L |
| 6 | H2PO4- | mg dihydrogen phosphate per L |

The fertilizers, in order, are Ca(NO3)2, KNO3, K2SO4, Mg(NO3)2, MgSO4, and
KH2PO4. The configured formulas are anhydrous and have 100 percent purity.

## Mass balance

Let `g[j]` be grams of fertilizer j, `V` the entered solution volume in liters,
`s[i,j]` the number of ions i per fertilizer formula unit, `M_ion[i]` its molar
mass, and `M_fert[j]` the fertilizer molar mass. Then:

```text
R[i,j] = (1000 / V) * s[i,j] * M_ion[i] / M_fert[j]
added_concentration = R @ g
predicted_final = current + added_concentration
```

`R` has units mg/L per gram of fertilizer. Potassium contributed by KH2PO4 is
included; sulfate is treated as the full sulfate ion rather than elemental S.
The model does not enforce pH-dependent phosphate speciation, precipitation,
solubility limits, activity coefficients, uptake, or any future time evolution.

## Objective

For each ion, define `scale[i] = max(target[i], 1.0)` in mg/L. Solve:

```text
minimize sum(((current + R @ g - target) / scale)**2)
subject to g >= 0
```

The 1 mg/L floor avoids division by zero. This is relative-error scaling for
targets of at least 1 mg/L and absolute-error scaling below that value. It is a
declared design choice, not a biological tolerance or a measured uncertainty.

The right-hand side retains signed `target - current`. Initial excess is not
silently removed or clamped away. A fertilizer supplying a deficient ion can
also increase another ion already above target; that tradeoff is included in
the objective and reported in final concentration errors.

SciPy's [nonnegative least squares solver](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.nnls.html)
provides the constrained solution. The six salt columns are not necessarily
independent, so multiple fertilizer blends can produce the same optimal ion
concentrations. This version does not add a cost, sparsity, or minimum-total-mass
tie-breaking objective. Its recommendation is one valid optimum.

## Stock volumes

For a stock strength `S[j]` in grams of fertilizer per liter of stock:

```text
stock_volume_ml[j] = 1000 * g[j] / S[j]
```

A blank/null stock strength returns no stock-volume estimate for that fertilizer.
It does not remove the fertilizer from consideration. Calculated stock volumes
do not increase `V` in the prediction; the calculation uses a fixed working
volume and does not model dilution.

## Metrics

- `error`: predicted final minus target in mg/L (positive means excess).
- `relative_error_percent`: 100 * error / target; null for a zero target.
- `rmse_mg_l`: square root of the mean squared error over all six ions.
- `max_abs_error_mg_l`: largest absolute concentration error.
- `weighted_rmse`: square root of the mean squared scaled residual used in the objective.
- `total_fertilizer_g`: sum of the six recommended dry masses.

Warnings describe initial excess, residual target mismatch, and assumptions where
applicable. They do not claim that any residual is an agronomically safe range.

## Product composition

Most practical fertilizer products should be checked against their label. For a
hydrated salt, its molar mass must include the hydration water. For mixtures or
impure products, a measured/label-based nutrient mass-fraction model may be more
appropriate than a single ideal formula. Adjust the backend chemistry and the
independent tests together; do not correct output masses only in the interface.
