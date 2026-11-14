import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { authApi } from "../services/authApi";

const AuthContext = createContext(null);
const SESSION_TOKEN_KEY = "studyai.session-token";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const clearSession = useCallback(() => {
    window.sessionStorage.removeItem(SESSION_TOKEN_KEY);
    setToken(null);
    setUser(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    let active = true;
    const savedToken = window.sessionStorage.getItem(SESSION_TOKEN_KEY);
    const handleUnauthorized = () => clearSession();
    window.addEventListener("studyai:unauthorized", handleUnauthorized);

    // Après un rechargement, le jeton est revérifié auprès de l'API avant d'ouvrir l'espace privé.
    if (!savedToken) {
      setLoading(false);
      return () => {
        active = false;
        window.removeEventListener("studyai:unauthorized", handleUnauthorized);
      };
    }

    authApi
      .currentUser(savedToken)
      .then((profile) => {
        if (!active) return;
        setToken(savedToken);
        setUser(profile);
        setError("");
      })
      .catch((requestError) => {
        if (!active) return;
        if (requestError.status === 401) clearSession();
        else setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      window.removeEventListener("studyai:unauthorized", handleUnauthorized);
    };
  }, [clearSession]);

  async function signIn(credentials) {
    const session = await authApi.login(credentials);
    const profile = await authApi.currentUser(session.access_token);
    // Le jeton reste limité à cette session de navigateur et n'est pas conservé dans localStorage.
    window.sessionStorage.setItem(SESSION_TOKEN_KEY, session.access_token);
    setToken(session.access_token);
    setUser(profile);
    setError("");
    setLoading(false);
    return profile;
  }

  async function register(credentials) {
    return authApi.register(credentials);
  }

  async function signOut() {
    try {
      if (token) await authApi.logout(token);
    } finally {
      clearSession();
    }
  }

  const value = useMemo(
    () => ({ token, user, loading, error, signIn, register, signOut }),
    [token, user, loading, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé dans AuthProvider.");
  return context;
}
