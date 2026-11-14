import { apiRequest } from "./api";

export const studyGuideApi = {
  list: (token, documentId) =>
    apiRequest(`/documents/${documentId}/study-guides`, {
      token,
    }),
  generate: (token, documentId, kind) =>
    apiRequest(`/documents/${documentId}/study-guide`, {
      method: "POST",
      token,
      body: { kind },
    }),
};
