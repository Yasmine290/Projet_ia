import { apiRequest } from "./api";

export const documentsApi = {
  listForCourse: (token, courseId) => apiRequest(`/courses/${courseId}/documents`, { token }),
  upload: (token, courseId, file) => {
    const body = new FormData();
    body.append("file", file);
    return apiRequest(`/courses/${courseId}/documents`, {
      method: "POST",
      token,
      body,
    });
  },
  index: (token, documentId) =>
    apiRequest(`/documents/${documentId}/index`, { method: "POST", token }),
  remove: (token, documentId) =>
    apiRequest(`/documents/${documentId}`, { method: "DELETE", token }),
};
