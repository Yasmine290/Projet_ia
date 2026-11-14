import { apiRequest } from "./api";

export const studyGuideApi = {
  generate: (token, documentId, kind) =>
    apiRequest(`/documents/${documentId}/study-guide`, {
      method: "POST",
      token,
      body: { kind },
    }),
};
