"use client"
import { useRef, useState, DragEvent } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"

export function UploadDropzone() {
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const handleFile = async (file: File) => {
    setError(null)
    if (!file.name.endsWith(".docx")) {
      setError("Only .docx files are supported")
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("File must be under 10MB")
      return
    }
    setUploading(true)
    try {
      const { id } = await api.uploadArticle(file)
      router.push(`/articles/${id}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed")
      setUploading(false)
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="w-full">
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`
          border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
          ${dragging ? "border-amber-500 bg-amber-50" : "border-gray-300 hover:border-amber-400 hover:bg-gray-50"}
          ${uploading ? "opacity-50 pointer-events-none" : ""}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".docx"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
        <p className="text-2xl mb-2">📄</p>
        <p className="text-gray-700 font-medium">
          {uploading ? "Uploading…" : "Drop your .docx file here or click to browse"}
        </p>
        <p className="text-sm text-gray-400 mt-1">Max 10MB · .docx only</p>
      </div>
      {error && (
        <p className="mt-3 text-sm text-red-600 text-center">{error}</p>
      )}
    </div>
  )
}
