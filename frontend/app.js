"use strict";

const form = document.querySelector("#calculatorForm");
const calculateButton = document.querySelector("#calculateButton");
const errorBanner = document.querySelector("#formError");
const resultsSection = document.querySelector("#results");

const numberFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 3,
  minimumFractionDigits: 0,
});

function formatNumber(value, suffix = "") {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return `${numberFormatter.format(value)}${suffix}`;
}

function readNumber(input, { blankAsZero = false, optional = false } = {}) {
  const rawValue = input.value.trim();
  if (rawValue === "") {
    if (optional) return null;
    if (blankAsZero) return 0;
    throw new Error("Complete all required fields before calculating.");
  }

  const value = Number(rawValue);
  if (!Number.isFinite(value) || !input.checkValidity()) {
    throw new Error("Enter valid, non-negative numbers within the allowed range.");
  }
  return value;
}

function buildPayload() {
  return {
    current: [...document.querySelectorAll(".current-input")].map((input) =>
      readNumber(input, { blankAsZero: true })
    ),
    target: [...document.querySelectorAll(".target-input")].map((input) =>
      readNumber(input)
    ),
    reservoir_volume: readNumber(document.querySelector("#reservoirVolume")),
    stock_concentrations: [...document.querySelectorAll(".stock-input")].map(
      (input) => readNumber(input, { optional: true })
    ),
  };
}

function setLoading(isLoading) {
  calculateButton.disabled = isLoading;
  calculateButton.classList.toggle("loading", isLoading);
  calculateButton.querySelector(".button-label").textContent = isLoading
    ? "Calculating…"
    : "Calculate recommendation";
}

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.hidden = false;
  errorBanner.focus();
}

function clearError() {
  errorBanner.hidden = true;
  errorBanner.textContent = "";
}

function appendCell(row, value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value;
  if (className) cell.className = className;
  row.append(cell);
  return cell;
}

function renderFertilizers(fertilizers) {
  const tableBody = document.querySelector("#fertilizerResults");
  const zeroMessage = document.querySelector("#zeroAdditionMessage");
  const recommended = fertilizers.filter((fertilizer) => fertilizer.recommended);
  tableBody.replaceChildren();

  for (const fertilizer of recommended) {
    const row = document.createElement("tr");
    appendCell(row, fertilizer.name);
    appendCell(row, formatNumber(fertilizer.mg_L, " mg/L"), "muted-value");
    appendCell(row, formatNumber(fertilizer.mass_g, " g"), "primary-value");
    appendCell(row, formatNumber(fertilizer.stock_volume_ml, " mL"));
    tableBody.append(row);
  }

  zeroMessage.hidden = recommended.length !== 0;
  tableBody.closest(".table-scroll").hidden = recommended.length === 0;
}

function renderFinalConcentrations(nutrients) {
  const tableBody = document.querySelector("#finalResults");
  tableBody.replaceChildren();

  for (const nutrient of nutrients) {
    const row = document.createElement("tr");
    appendCell(row, nutrient.display_name);
    appendCell(row, formatNumber(nutrient.current_mg_L, " mg/L"));
    appendCell(row, formatNumber(nutrient.target_mg_L, " mg/L"));
    appendCell(row, formatNumber(nutrient.final_mg_L, " mg/L"), "primary-value");

    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = `fit-badge${nutrient.fit_status === "close" ? "" : " outside"}`;
    status.textContent = nutrient.fit_status === "close" ? "Close" : "Review";
    statusCell.append(status);
    row.append(statusCell);
    tableBody.append(row);
  }
}

function renderBalance(nutrients) {
  const tableBody = document.querySelector("#balanceResults");
  tableBody.replaceChildren();

  for (const nutrient of nutrients) {
    const row = document.createElement("tr");
    appendCell(row, nutrient.display_name);
    appendCell(row, formatNumber(nutrient.requested_increase_mg_L, " mg/L"));
    appendCell(row, formatNumber(nutrient.predicted_increase_mg_L, " mg/L"));
    const differenceClass = nutrient.difference_mg_L > 0 ? "positive-difference" : "";
    const sign = nutrient.difference_mg_L > 0 ? "+" : "";
    appendCell(
      row,
      `${sign}${formatNumber(nutrient.difference_mg_L, " mg/L")}`,
      differenceClass
    );
    tableBody.append(row);
  }
}

function renderWarnings(warnings) {
  const warningList = document.querySelector("#warningList");
  warningList.replaceChildren();

  for (const warning of warnings) {
    const item = document.createElement("div");
    item.className = "warning-item";
    const icon = document.createElement("span");
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "!";
    const message = document.createElement("p");
    message.textContent = warning.message;
    item.append(icon, message);
    warningList.append(item);
  }
}

function renderResults(data) {
  renderFertilizers(data.fertilizers);
  renderFinalConcentrations(data.nutrients);
  renderBalance(data.nutrients);
  renderWarnings(data.warnings);

  document.querySelector("#summaryReservoir").textContent = formatNumber(
    data.reservoir_volume_L,
    " L"
  );
  document.querySelector("#summaryCombination").textContent =
    data.best_combination.join(" + ");

  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function apiErrorMessage(payload) {
  const error = payload?.error;
  if (!error) return "The server returned an unexpected response.";
  if (Array.isArray(error.details) && error.details.length > 0) {
    const firstDetail = error.details[0];
    const field = firstDetail.field ? `${firstDetail.field}: ` : "";
    return `${field}${firstDetail.message}`;
  }
  return error.message || "The calculation could not be completed.";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();

  let payload;
  try {
    payload = buildPayload();
  } catch (error) {
    showError(error.message);
    return;
  }

  setLoading(true);
  try {
    const response = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(apiErrorMessage(data));
    }
    renderResults(data);
  } catch (error) {
    resultsSection.hidden = true;
    showError(
      error instanceof TypeError
        ? "The calculation service is unavailable. Check the server and try again."
        : error.message
    );
  } finally {
    setLoading(false);
  }
});

form.addEventListener("reset", () => {
  clearError();
  resultsSection.hidden = true;
});
