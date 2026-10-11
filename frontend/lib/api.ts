const TOKEN_KEY = "met_token";
const USER_KEY = "met_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): any | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setAuth(token: string, user: any) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function updateUser(user: any) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

export async function api<T = any>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string>),
  };
  if (opts.body) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(`/api/v1${path}`, { ...opts, headers });
  if (resp.status === 401) {
    clearAuth();
    if (!location.pathname.startsWith("/login")) {
      location.href = "/login";
    }
    throw new ApiError(401, "未登录");
  }
  if (!resp.ok) {
    let detail = `请求失败 (${resp.status})`;
    try {
      const data = await resp.json();
      detail = data.detail || detail;
    } catch {}
    throw new ApiError(resp.status, detail);
  }
  return resp.json();
}
