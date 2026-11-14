import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "./AuthContext";
import { coursesApi } from "../services/coursesApi";
import { documentsApi } from "../services/documentsApi";

const StudyDataContext = createContext(null);

export function StudyDataProvider({ children }) {
  const { token, user } = useAuth();
  const [courses, setCourses] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  const refresh = useCallback(() => setRevision((current) => current + 1), []);

  useEffect(() => {
    let active = true;
    if (!token || !user) {
      setCourses([]);
      setDocuments([]);
      setError("");
      setLoading(false);
      return () => {
        active = false;
      };
    }

    async function loadStudyData() {
      setLoading(true);
      setError("");
      try {
        const nextCourses = await coursesApi.list(token);
        // L'API liste les documents par cours ; les requêtes partent en parallèle.
        const documentsByCourse = await Promise.all(
          nextCourses.map((course) => documentsApi.listForCourse(token, course.id)),
        );
        if (!active) return;
        setCourses(nextCourses);
        setDocuments(documentsByCourse.flat());
      } catch (requestError) {
        if (active) setError(requestError.message);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadStudyData();
    return () => {
      active = false;
    };
  }, [token, user, revision]);

  const value = useMemo(
    () => ({ courses, documents, loading, error, refresh }),
    [courses, documents, loading, error, refresh],
  );

  return <StudyDataContext.Provider value={value}>{children}</StudyDataContext.Provider>;
}

export function useStudyData() {
  const context = useContext(StudyDataContext);
  if (!context) throw new Error("useStudyData doit être utilisé dans StudyDataProvider.");
  return context;
}
