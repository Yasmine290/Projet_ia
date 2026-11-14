import { apiRequest } from "./api";

export const coursesApi = {
  list: (token) => apiRequest("/courses", { token }),
  create: (token, course) => apiRequest("/courses", { method: "POST", token, body: course }),
  update: (token, courseId, changes) =>
    apiRequest(`/courses/${courseId}`, { method: "PATCH", token, body: changes }),
  remove: (token, courseId) => apiRequest(`/courses/${courseId}`, { method: "DELETE", token }),
};
