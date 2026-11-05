"use strict";

(() => {
  // Display metadata and example inputs only. All fertilizer chemistry and
  // optimization are implemented by the Python API.
  const IONS = [
    { id: "nitrate", label: "Nitrate", formula: "NO₃⁻" },
    { id: "potassium", label: "Potassium", formula: "K⁺" },
    { id: "calcium", label: "Calcium", formula: "Ca²⁺" },
    { id: "magnesium", label: "Magnesium", formula: "Mg²⁺" },
    { id: "sulfate", label: "Sulfate", formula: "SO₄²⁻" },
    { id: "dihydrogen_phosphate", label: "Dihydrogen phosphate", formula: "H₂PO₄⁻" },
  ];
  const FERTILIZERS = [
    { id: "calcium_nitrate", name: "Calcium nitrate", formula: "Ca(NO₃)₂" },
    { id: "potassium_nitrate", name: "Potassium nitrate", formula: "KNO₃" },
    { id: "potassium_sulfate", name: "Potassium sulfate", formula: "K₂SO₄" },
    { id: "magnesium_nitrate", name: "Magnesium nitrate", formula: "Mg(NO₃)₂" },
    { id: "magnesium_sulfate", name: "Magnesium sulfate", formula: "MgSO₄" },
    { id: "monopotassium_phosphate", name: "Monopotassium phosphate", formula: "KH₂PO₄" },
  ];
  const EXAMPLE = {
    target: [434, 117.3, 80.2, 24.6, 96, 50],
    current: [380, 100, 70, 20, 80, 40],
    reservoir_volume: 80,
    stock_concentrations: [100, 100, 100, 100, 100, 100],
  };
  const byId = (id) => document.getElementById(id);
  const form = byId("calculator-form");
  const format = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
  const massFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
  let latestResult = null;
  let latestPayload = null;
  let latestCalculatedAt = null;
  let busy = false;
  let setupError = "";
  let apiBase = "";
  let healthController = null;
  let editRevision = 0;

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function makeInput(id, name, labelledBy, optional = false) {
    const input = element("input");
    input.id = id;
    input.name = name;
    input.type = "number";
    input.min = "0";
    input.step = "any";
    input.inputMode = "decimal";
    input.required = !optional;
    input.setAttribute("aria-labelledby", labelledBy);
    if (optional) input.placeholder = "Optional";
    return input;
  }

  function createInputs() {
    const ionBody = byId("ion-inputs");
    IONS.forEach((ion) => {
      const row = element("tr");
      const name = element("th");
      name.scope = "row";
      name.id = `ion-${ion.id}`;
      name.append(element("span", "ion-name", ion.label), element("span", "chemical-formula", ion.formula));
      row.append(name);
      ["target", "current"].forEach((kind) => {
        const cell = element("td");
        cell.append(makeInput(`${kind}-${ion.id}`, `${kind}_${ion.id}`, `ion-${ion.id} ${kind}-heading`));
        row.append(cell);
      });
      ionBody.append(row);
    });
    const stockBody = byId("stock-inputs");
    FERTILIZERS.forEach((fertilizer) => {
      const row = element("tr");
      const name = element("th");
      name.scope = "row";
      name.id = `fertilizer-${fertilizer.id}`;
      name.append(element("span", "fertilizer-name", fertilizer.name), element("span", "chemical-formula", fertilizer.formula));
      const cell = element("td");
      cell.append(makeInput(`stock-${fertilizer.id}`, `stock_${fertilizer.id}`, `fertilizer-${fertilizer.id} stock-heading`, true));
      row.append(name, cell);
      stockBody.append(row);
    });
  }

  function setConnection(state, label) {
    byId("connection-status").dataset.state = state;
    byId("connection-label").textContent = label;
  }

  function configureApi() {
    const configured = window.APP_CONFIG?.apiBaseUrl;
    if (configured !== undefined && typeof configured !== "string") {
      throw new Error("The API address in frontend/config.js must be a text value.");
    }
    const value = (configured || "").trim();
    if (!value) {
      if (location.hostname === "github.io" || location.hostname.endsWith(".github.io")) {
        throw new Error("The backend address has not been set. Set the GitHub Actions repository variable API_BASE_URL to your deployed HTTPS backend origin, then rerun the publishing workflow. For a manual deployment, set apiBaseUrl in frontend/config.js.");
      }
      if (!["http:", "https:"].includes(location.protocol)) {
        throw new Error("Open this calculator through the local FastAPI server or a hosted website. Opening index.html directly cannot run calculations.");
      }
      return "";
    }
    let parsed;
    try { parsed = new URL(value); } catch { throw new Error("The API address in frontend/config.js must be a complete URL, such as https://your-service.onrender.com."); }
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname);
    if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && local)) {
      throw new Error("Use an HTTPS backend address. HTTP is allowed only for a local development server.");
    }
    if (parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname !== "/") {
      throw new Error("Set apiBaseUrl to the backend origin only, without credentials, a path, query parameters, or a fragment.");
    }
    return parsed.origin;
  }

  function showError(message) {
    byId("error-message").textContent = message;
    byId("error-message").hidden = false;
  }

  function hideError() {
    byId("error-message").hidden = true;
    byId("error-message").textContent = "";
  }

  function clearInvalid() {
    form.querySelectorAll("input").forEach((input) => input.removeAttribute("aria-invalid"));
  }

  function markEdited() {
    editRevision += 1;
    byId("input-mode").textContent = "Edited inputs";
    if (latestResult) byId("stale-message").hidden = false;
  }

  function fillExample() {
    IONS.forEach((ion, index) => {
      byId(`target-${ion.id}`).value = EXAMPLE.target[index];
      byId(`current-${ion.id}`).value = EXAMPLE.current[index];
    });
    FERTILIZERS.forEach((fertilizer, index) => { byId(`stock-${fertilizer.id}`).value = EXAMPLE.stock_concentrations[index]; });
    byId("reservoir-volume").value = EXAMPLE.reservoir_volume;
    markEdited();
    byId("input-mode").textContent = "Example inputs";
    clearInvalid();
    if (!setupError) hideError();
  }

  function numericValue(id, label, { positive = false, optional = false } = {}) {
    const input = byId(id);
    const raw = input.value.trim();
    if (optional && raw === "" && !input.validity.badInput) return null;
    const number = input.valueAsNumber;
    if (raw === "" || !Number.isFinite(number) || number < 0 || (positive && number <= 0)) {
      input.setAttribute("aria-invalid", "true");
      input.focus();
      throw new Error(`${label} must be ${positive ? "a number greater than zero" : "a number of zero or greater"}.`);
    }
    return number;
  }

  function readPayload() {
    clearInvalid();
    return {
      target: IONS.map((ion) => numericValue(`target-${ion.id}`, `${ion.label} target`)),
      current: IONS.map((ion) => numericValue(`current-${ion.id}`, `${ion.label} current concentration`)),
      reservoir_volume: numericValue("reservoir-volume", "Reservoir volume", { positive: true }),
      stock_concentrations: FERTILIZERS.map((fertilizer) => numericValue(`stock-${fertilizer.id}`, `${fertilizer.name} stock strength`, { positive: true, optional: true })),
    };
  }

  function setBusy(value) {
    busy = value;
    byId("calculate-button").disabled = value || Boolean(setupError);
    byId("calculate-label").textContent = value ? "Calculating…" : "Calculate additions";
    byId("example-button").disabled = value;
    byId("clear-button").disabled = value;
    byId("results").setAttribute("aria-busy", String(value));
  }

  function formatValidationError(data) {
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.message === "string") return data.message;
    if (!Array.isArray(data?.detail)) return "The API could not process this request. Check the inputs and try again.";
    return data.detail.slice(0, 4).map((issue) => {
      const path = Array.isArray(issue.loc) ? issue.loc.filter((part) => part !== "body").join(" → ") : "Input";
      return `${path}: ${typeof issue.msg === "string" ? issue.msg : "Invalid value"}`;
    }).join(". ");
  }

  async function checkHealth() {
    healthController = new AbortController();
    const controller = healthController;
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(`${apiBase}/api/health`, { signal: controller.signal, cache: "no-store" });
      if (!response.ok) throw new Error("Unavailable");
      const data = await response.json();
      if (data.status !== "ok") throw new Error("Unavailable");
      if (!busy) setConnection("online", "Calculation service ready");
    } catch {
      if (healthController === controller && !busy && !latestResult) setConnection("offline", "Service not yet available");
    } finally { clearTimeout(timer); }
  }

  function validateResponse(data) {
    const numericFields = ["target", "current", "added", "final", "error"];
    if (!data || !Array.isArray(data.ions) || data.ions.length !== 6 || !Array.isArray(data.fertilizers) || data.fertilizers.length !== 6 || !data.metrics) {
      throw new Error("The API returned an unexpected result format. Check that this frontend and backend are from the same release.");
    }
    if (!data.ions.every((ion, index) => ion && ion.id === IONS[index].id && numericFields.every((key) => typeof ion[key] === "number" && Number.isFinite(ion[key]))) ||
        !data.fertilizers.every((fertilizer, index) => fertilizer && fertilizer.id === FERTILIZERS[index].id && Number.isFinite(fertilizer.grams) && fertilizer.grams >= 0 && (fertilizer.stock_volume_ml === null || (Number.isFinite(fertilizer.stock_volume_ml) && fertilizer.stock_volume_ml >= 0))) ||
        !["total_fertilizer_g", "rmse_mg_l", "max_abs_error_mg_l"].every((key) => Number.isFinite(data.metrics[key]))) {
      throw new Error("The API returned invalid numeric values. No formulation has been displayed.");
    }
    return {
      ...data,
      warnings: Array.isArray(data.warnings) ? data.warnings.filter((item) => typeof item === "string") : [],
      assumptions: Array.isArray(data.assumptions) ? data.assumptions.filter((item) => typeof item === "string") : [],
    };
  }

  function signedValue(value) {
    const rounded = Math.round(value * 100) / 100;
    return `${rounded > 0 ? "+" : ""}${format.format(Object.is(rounded, -0) ? 0 : rounded)}`;
  }

  function renderResult(data, payload, requestRevision) {
    const doses = byId("dosing-results");
    const balance = byId("balance-results");
    doses.replaceChildren();
    balance.replaceChildren();
    data.fertilizers.forEach((fertilizer, index) => {
      const row = element("tr");
      const name = element("th");
      name.scope = "row";
      name.append(element("span", "fertilizer-name", fertilizer.name || FERTILIZERS[index].name), element("span", "chemical-formula", FERTILIZERS[index].formula));
      row.append(name, element("td", fertilizer.grams > 0 ? "dose-value" : "dose-zero", massFormat.format(fertilizer.grams)), element("td", "", fertilizer.stock_volume_ml === null ? "—" : format.format(fertilizer.stock_volume_ml)));
      doses.append(row);
    });
    data.ions.forEach((ion, index) => {
      const row = element("tr");
      const heading = element("th", "", IONS[index].formula);
      heading.scope = "row";
      heading.title = IONS[index].label;
      row.append(heading, element("td", "", format.format(ion.current)), element("td", "", format.format(ion.target)), element("td", "", format.format(ion.added)), element("td", "final-concentration", format.format(ion.final)), element("td", ion.error > 0.005 ? "difference-positive" : ion.error < -0.005 ? "difference-negative" : "", signedValue(ion.error)));
      balance.append(row);
    });
    byId("total-mass").textContent = massFormat.format(data.metrics.total_fertilizer_g);
    byId("tracking-rmse").textContent = format.format(data.metrics.rmse_mg_l);
    byId("max-error").textContent = format.format(data.metrics.max_abs_error_mg_l);
    byId("result-context").textContent = `Calculated for ${format.format(payload.reservoir_volume)} L of solution.`;
    const warnings = Array.isArray(data.warnings) ? data.warnings.filter((item) => typeof item === "string") : [];
    byId("warnings-list").replaceChildren(...warnings.map((warning) => element("li", "", warning)));
    byId("warnings-panel").hidden = warnings.length === 0;
    const assumptions = Array.isArray(data.assumptions) ? data.assumptions.filter((item) => typeof item === "string") : [];
    byId("assumptions-list").replaceChildren(...assumptions.map((assumption) => element("li", "", assumption)));
    byId("empty-state").hidden = true;
    byId("results").hidden = false;
    byId("stale-message").hidden = requestRevision === editRevision;
    latestResult = data;
    latestPayload = JSON.parse(JSON.stringify(payload));
    latestCalculatedAt = new Date();
    byId("calculation-status").textContent = "Calculation complete. Review the predicted ion balance and formulation notes.";
    byId("results-title").focus({ preventScroll: true });
    if (window.matchMedia("(max-width: 850px)").matches) byId("results").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function calculate(event) {
    event.preventDefault();
    if (busy) return;
    if (setupError) { showError(setupError); return; }
    hideError();
    let payload;
    try { payload = readPayload(); } catch (error) { showError(error.message); return; }
    const requestRevision = editRevision;
    if (healthController) { healthController.abort(); healthController = null; }
    setBusy(true);
    setConnection("checking", "Calculating");
    byId("calculation-status").textContent = "Calculating fertilizer additions…";
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000);
    const progressTimer = setTimeout(() => { byId("calculation-status").textContent = "Waiting for the calculation service. A sleeping service may need time to start."; }, 8000);
    try {
      const response = await fetch(`${apiBase}/api/calculate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      let data;
      try { data = await response.json(); } catch {
        throw new Error("The calculation service did not return JSON. Check the API address in frontend/config.js and confirm the backend is running.");
      }
      if (!response.ok) throw new Error(response.status >= 500 ? "The calculation service encountered an error. Please try again or check the server logs." : formatValidationError(data));
      renderResult(validateResponse(data), payload, requestRevision);
      setConnection("online", "Calculation service ready");
    } catch (error) {
      byId("calculation-status").textContent = "";
      const message = error.name === "AbortError"
        ? "The calculation service did not respond within 60 seconds. It may be starting; please try again."
        : error instanceof TypeError
          ? "Could not connect to the calculation service. Check your connection, the backend address, and the server's CORS_ORIGINS setting."
          : error.message;
      showError(message);
      setConnection("offline", "Calculation unavailable");
    } finally {
      clearTimeout(timer);
      clearTimeout(progressTimer);
      setBusy(false);
    }
  }

  function csvCell(value) {
    if (value === null || value === undefined) return "";
    if (typeof value === "number") return String(value);
    let text = String(value);
    if (/^[=+@-]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  }

  function exportCsv() {
    if (!latestResult || !latestPayload) return;
    const rows = [
      ["Nutrient Solution Calculator"],
      ["Calculated at", latestCalculatedAt.toISOString()],
      ["Reservoir volume (L)", latestPayload.reservoir_volume],
      ["RMSE (mg/L)", latestResult.metrics.rmse_mg_l],
      ["Maximum absolute error (mg/L)", latestResult.metrics.max_abs_error_mg_l],
      [],
      ["Fertilizer", "Formula (anhydrous)", "Dry mass (g)", "Stock strength (g/L)", "Stock volume (mL)"],
      ...latestResult.fertilizers.map((item, index) => [item.name || FERTILIZERS[index].name, item.formula || FERTILIZERS[index].formula, item.grams, latestPayload.stock_concentrations[index], item.stock_volume_ml]),
      [],
      ["Ion", "Current (mg/L)", "Target (mg/L)", "Added (mg/L)", "Predicted (mg/L)", "Difference (mg/L)"],
      ...latestResult.ions.map((ion, index) => [IONS[index].label, ion.current, ion.target, ion.added, ion.final, ion.error]),
      [],
      ["Formulation notes"],
      ...(latestResult.warnings || []).map((warning) => [warning]),
      [],
      ["Assumptions"],
      ...(latestResult.assumptions || []).map((assumption) => [assumption]),
    ];
    const content = "\uFEFF" + rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8;" }));
    const link = element("a");
    link.href = url;
    link.download = `nutrient-formulation-${latestCalculatedAt.toISOString().slice(0, 10)}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  createInputs();
  fillExample();
  form.addEventListener("submit", calculate);
  form.addEventListener("input", (event) => {
    if (event.target instanceof HTMLInputElement) {
      event.target.removeAttribute("aria-invalid");
      markEdited();
    }
  });
  byId("example-button").addEventListener("click", fillExample);
  byId("clear-button").addEventListener("click", () => {
    form.querySelectorAll("input").forEach((input) => { input.value = ""; });
    clearInvalid();
    markEdited();
    if (!setupError) hideError();
    byId("reservoir-volume").focus();
  });
  byId("export-button").addEventListener("click", exportCsv);
  try { apiBase = configureApi(); checkHealth(); } catch (error) {
    setupError = error.message;
    setConnection("setup", "Backend setup needed");
    showError(setupError);
    setBusy(false);
  }
})();
