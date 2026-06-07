import { api } from "@/lib/api"
import { UploadDropzone } from "@/components/UploadDropzone"
import { ArticleList } from "@/components/ArticleList"

export const dynamic = "force-dynamic"

export default async function HomePage() {
  const articles = await api.listArticles().catch(() => [])

  return (
    <main className="max-w-3xl mx-auto px-4 py-16">
      <div className="mb-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Article Generator</h1>
        <p className="text-gray-500">Upload rough travel notes and get a structured magazine article.</p>
      </div>

      <UploadDropzone />

      <div className="mt-16">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">Saved articles</h2>
        <ArticleList articles={articles} />
      </div>
    </main>
  )
}
