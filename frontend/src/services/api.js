// En local, Vite relaie /api vers FastAPI ; une variable d'environnement peut remplacer cette valeur.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getErrorMessage(payload, status) {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg)
      .filter(Boolean)
      .join(" ");
  }
  return `La requête a échoué (HTTP ${status}).`;
}

export async function apiRequest(path, { token, method = "GET", body, signal } = {}) {
  const headers = new Headers({ Accept: "application/json" });
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let requestBody;
  if (body instanceof FormData) {
    // Le navigateur doit définir lui-même la boundary multipart du formulaire.
    requestBody = body;
  } else if (body !== undefined) {
    headers.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: requestBody,
      signal,
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError("Impossible de joindre l'API. Vérifiez que le backend fonctionne.", 0);
    }
    throw error;
  }

  if (response.status === 401) {
    // Le contexte d'authentification écoute cet événement pour effacer la session expirée.
    window.dispatchEvent(new Event("studyai:unauthorized"));
  }
  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    throw new ApiError(getErrorMessage(payload, response.status), response.status);
  }
  return payload;
}
