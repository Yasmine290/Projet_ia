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

export async function apiEventStream(path, { token, method = "GET", body, signal, onEvent } = {}) {
  const headers = new Headers({ Accept: "text/event-stream" });
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let requestBody;
  if (body instanceof FormData) {
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
    window.dispatchEvent(new Event("studyai:unauthorized"));
  }
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
    throw new ApiError(getErrorMessage(payload, response.status), response.status);
  }
  if (!response.headers.get("content-type")?.includes("text/event-stream") || !response.body) {
    throw new ApiError("L'API n'a pas ouvert le flux de réponse attendu.", 502);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  function dispatchEvent(block) {
    const data = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) return;

    let event;
    try {
      event = JSON.parse(data);
    } catch {
      throw new ApiError("L'API a envoyé un événement de réponse invalide.", 502);
    }
    onEvent?.(event);
  }

  try {
    let done = false;
    while (!done) {
      const chunk = await reader.read();
      done = chunk.done;
      buffer += decoder.decode(chunk.value, { stream: !done });
      let separator = buffer.match(/\r?\n\r?\n/);
      while (separator) {
        dispatchEvent(buffer.slice(0, separator.index));
        buffer = buffer.slice(separator.index + separator[0].length);
        separator = buffer.match(/\r?\n\r?\n/);
      }
    }
    if (buffer.trim()) dispatchEvent(buffer);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError("La connexion au flux de réponse a été interrompue.", 0);
    }
    throw error;
  } finally {
    reader.releaseLock();
  }
}
