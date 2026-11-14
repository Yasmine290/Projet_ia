import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "../context/AuthContext";
import { LoadingState } from "../components/ui";
import { StudyDataProvider } from "../context/StudyDataContext";

export default function ProtectedLayout() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <LoadingState label="Vérification de la session…" />;
  if (!user) {
    return <Navigate to="/connexion" replace state={{ from: location.pathname }} />;
  }

  return (
    <StudyDataProvider>
      <Outlet />
    </StudyDataProvider>
  );
}
