import { createBrowserRouter } from "react-router";
import LoginPage from "../pages/LoginPage";
import DashboardPage from "../pages/DashboardPage";
import CoursesPage from "../pages/CoursesPage";
import DocumentsPage from "../pages/DocumentsPage";
import AssistantPage from "../pages/AssistantPage";
import SummariesPage from "../pages/SummariesPage";
import ComingSoonPage from "../pages/ComingSoonPage";
import NotFoundPage from "../pages/NotFoundPage";
import SettingsPage from "../pages/SettingsPage";
import ProtectedLayout from "../layouts/ProtectedLayout";
import AppLayout from "../layouts/AppLayout";
import { LoadingState } from "../components/ui";

export const router = createBrowserRouter([
  {
    path: "/connexion",
    Component: LoginPage,
  },
  {
    path: "/",
    Component: ProtectedLayout,
    HydrateFallback: () => <LoadingState label="Chargement de StudyAI…" />,
    children: [
      {
        Component: AppLayout,
        children: [
          { index: true, Component: DashboardPage },
          { path: "cours", Component: CoursesPage },
          { path: "documents", Component: DocumentsPage },
          { path: "assistant", Component: AssistantPage },
          { path: "resumes", Component: SummariesPage },
          { path: "parametres", Component: SettingsPage },
          // Ces espaces restent accessibles, mais sans contenu fictif tant que l'API n'existe pas.
          { path: "quiz", Component: ComingSoonPage },
          { path: "progression", Component: ComingSoonPage },
          { path: "revisions", Component: ComingSoonPage },
          { path: "*", Component: NotFoundPage },
        ],
      },
    ],
  },
]);
