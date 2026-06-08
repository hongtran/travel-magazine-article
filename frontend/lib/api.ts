const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export type ArticleStatus = "processing" | "completed" | "failed" | "rejected"

export interface BodySection {
  heading: string
  content: string
  source_quote: string
}

export interface KeyFact {
  label: string
  value: string
  source_quote: string
}

export interface ListItem {
  value: string
  source_quote: string
}

export interface Article {
  id: string
  status: ArticleStatus
  original_filename: string
  original_text: string
  title: string | null
  intro_hook: string | null
  intro_hook_source_quote: string | null
  body_sections: BodySection[] | null
  best_for: ListItem[] | null
  not_for: ListItem[] | null
  ethics_safety_notes: string | null
  ethics_safety_notes_source_quote: string | null
  key_facts: KeyFact[] | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ArticleListItem {
  id: string
  status: ArticleStatus
  original_filename: string
  title: string | null
  created_at: string
}

export interface ArticleStatusResponse {
  id: string
  status: ArticleStatus
  error_message: string | null
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  uploadArticle: (file: File): Promise<ArticleStatusResponse> => {
    const form = new FormData()
    form.append("file", file)
    return apiFetch("/articles", { method: "POST", body: form })
  },

  listArticles: (): Promise<ArticleListItem[]> =>
    apiFetch("/articles"),

  getArticle: (id: string): Promise<Article> =>
    apiFetch(`/articles/${id}`),

  getArticleStatus: (id: string): Promise<ArticleStatusResponse> =>
    apiFetch(`/articles/${id}/status`),

  updateArticle: (id: string, data: Partial<Article>): Promise<Article> =>
    apiFetch(`/articles/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  retryArticle: (id: string): Promise<ArticleStatusResponse> =>
    apiFetch(`/articles/${id}/retry`, { method: "POST" }),
}
