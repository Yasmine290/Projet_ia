import { apiRequest } from "./api";

export const authApi = {
  register: (credentials) => apiRequest("/auth/register", { method: "POST", body: credentials }),
  login: (credentials) => apiRequest("/auth/login", { method: "POST", body: credentials }),
  currentUser: (token) => apiRequest("/auth/me", { token }),
  logout: (token) => apiRequest("/auth/logout", { method: "POST", token }),
};
