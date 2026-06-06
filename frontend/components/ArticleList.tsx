"use client"
import Link from "next/link"
import { ArticleListItem } from "@/lib/api"

const STATUS_STYLES: Record<string, string> = {
  completed: "bg-green-100 text-green-800",
  processing: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
}

interface Props {
  articles: ArticleListItem[]
}

export function ArticleList({ articles }: Props) {
  if (articles.length === 0) {
    return <p className="text-gray-400 text-center py-8">No articles yet. Upload your first document above.</p>
  }

  return (
    <div className="divide-y divide-gray-100">
      {articles.map((article) => (
        <Link
          key={article.id}
          href={`/articles/${article.id}`}
          className="flex items-center justify-between py-4 px-2 hover:bg-gray-50 rounded-lg transition-colors group"
        >
          <div>
            <p className="font-medium text-gray-900 group-hover:text-amber-700 transition-colors">
              {article.title ?? article.original_filename}
            </p>
            <p className="text-sm text-gray-400">{article.original_filename}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_STYLES[article.status]}`}>
              {article.status}
            </span>
            <span className="text-xs text-gray-400">
              {new Date(article.created_at).toLocaleDateString()}
            </span>
          </div>
        </Link>
      ))}
    </div>
  )
}
