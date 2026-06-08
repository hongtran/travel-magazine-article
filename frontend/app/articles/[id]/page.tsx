"use client"
import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { Article, api } from "@/lib/api"
import { ArticleEditor } from "@/components/ArticleEditor"

export default function ArticlePage() {
  const { id } = useParams<{ id: string }>()
  const [article, setArticle] = useState<Article | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    let pollInterval: ReturnType<typeof setInterval> | null = null

    const loadArticle = async () => {
      try {
        const data = await api.getArticle(id)
        if (cancelled) return
        setArticle(data)

        if (data.status === "processing") {
          let polls = 0
          const MAX_POLLS = 150 // 5 minutes at 2s interval
          pollInterval = setInterval(async () => {
            if (++polls > MAX_POLLS) {
              clearInterval(pollInterval!)
              if (!cancelled) setError("Generation is taking longer than expected. Check back later.")
              return
            }
            try {
              const status = await api.getArticleStatus(id)
              if (cancelled) return
              if (status.status === "completed") {
                clearInterval(pollInterval!)
                const full = await api.getArticle(id)
                if (!cancelled) setArticle(full)
              } else if (status.status === "failed" || status.status === "rejected") {
                clearInterval(pollInterval!)
                setArticle((prev) => prev ? { ...prev, status: status.status, error_message: status.error_message } : prev)
              }
            } catch {
              // network blip — keep polling
            }
          }, 2000)
        }
      } catch {
        if (!cancelled) setError("Article not found")
      }
    }

    loadArticle()
    return () => {
      cancelled = true
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [id, retryKey])

  const handleRetry = async () => {
    setError(null)
    await api.retryArticle(id)
    setArticle((prev) => prev ? { ...prev, status: "processing", error_message: null } : prev)
    setRetryKey((k) => k + 1)
  }

  if (error) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-16 text-center">
        <p className="text-red-600 mb-4">{error}</p>
        <Link href="/" className="text-amber-600 hover:underline">← Back to home</Link>
      </main>
    )
  }

  if (!article) {
    return <ProcessingView message="Loading…" />
  }

  if (article.status === "processing") {
    return <ProcessingView message="Generating your article…" />
  }

  if (article.status === "failed" || article.status === "rejected") {
    return (
      <main className="max-w-2xl mx-auto px-4 py-16 text-center">
        <p className="text-red-600 font-medium mb-2">Generation failed</p>
        <p className="text-gray-500 text-sm mb-6">{article.error_message ?? "An unexpected error occurred."}</p>
        {article.status === "failed" && (
          <button
            onClick={handleRetry}
            className="bg-amber-600 text-white px-6 py-2 rounded-lg hover:bg-amber-700 transition-colors mr-4"
          >
            Retry
          </button>
        )}
        <Link href="/" className="text-gray-400 hover:text-gray-700">← Back</Link>
      </main>
    )
  }

  return (
    <div>
      <header className="sticky top-0 z-10 bg-white border-b border-gray-100 px-4 py-3 flex items-center justify-between">
        <Link href="/" className="text-sm text-gray-400 hover:text-gray-700 transition-colors">← All articles</Link>
        <span className={`text-xs font-medium transition-colors ${
          saveState === "saving" ? "text-amber-500" :
          saveState === "saved" ? "text-green-600" :
          saveState === "error" ? "text-red-500" : "text-transparent"
        }`}>
          {saveState === "saving" ? "Saving…" : saveState === "saved" ? "Saved" : saveState === "error" ? "Save failed" : "·"}
        </span>
      </header>
      <ArticleEditor initial={article} onSaveState={setSaveState} />
    </div>
  )
}

function ProcessingView({ message }: { message: string }) {
  return (
    <main className="max-w-2xl mx-auto px-4 py-16 text-center">
      <div className="animate-pulse">
        <div className="h-8 bg-gray-200 rounded mb-4 w-3/4 mx-auto" />
        <div className="h-4 bg-gray-200 rounded mb-2 w-full" />
        <div className="h-4 bg-gray-200 rounded mb-2 w-5/6 mx-auto" />
        <div className="h-4 bg-gray-200 rounded w-4/5 mx-auto" />
      </div>
      <p className="mt-8 text-sm text-gray-400">{message}</p>
    </main>
  )
}
