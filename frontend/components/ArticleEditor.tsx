"use client"
import { useState } from "react"
import { Article, ListItem, api } from "@/lib/api"
import { EditableField } from "./EditableField"
import { SourceChip } from "./SourceChip"

interface Props {
  initial: Article
  onSaveState?: (state: "idle" | "saving" | "saved" | "error") => void
}

export function ArticleEditor({ initial, onSaveState }: Props) {
  const [article, setArticle] = useState<Article>(initial)
  const [showOriginal, setShowOriginal] = useState(false)

  const save = async (field: keyof Article, value: unknown) => {
    onSaveState?.("saving")
    try {
      const updated = await api.updateArticle(article.id, { [field]: value } as Partial<Article>)
      setArticle(updated)
      onSaveState?.("saved")
    } catch (e) {
      onSaveState?.("error")
      throw e  // re-throw so EditableField can revert its local value
    }
  }

  return (
    <article className="max-w-2xl mx-auto px-4 py-12">
      {/* Title */}
      <EditableField
        value={article.title ?? ""}
        onSave={(v) => save("title", v)}
        placeholder="Article title"
        displayClassName="text-4xl font-bold text-gray-900 mb-6 leading-tight"
        className="text-4xl font-bold"
      />

      {/* Intro hook */}
      <div className="flex items-start gap-2 mb-10">
        <EditableField
          value={article.intro_hook ?? ""}
          onSave={(v) => save("intro_hook", v)}
          multiline
          placeholder="Write a compelling intro hook…"
          displayClassName="text-xl text-gray-600 leading-relaxed border-l-4 border-amber-400 pl-4 italic flex-1"
          className="text-xl flex-1"
        />
        <SourceChip quote={article.intro_hook_source_quote} />
      </div>

      {/* Body sections */}
      {(article.body_sections ?? []).map((section, i) => (
        <div key={i} className="mb-8">
          <div className="flex items-center gap-2 mb-2">
            <EditableField
              value={section.heading}
              onSave={(v) => {
                const sections = [...(article.body_sections ?? [])]
                sections[i] = { ...sections[i], heading: v }
                return save("body_sections", sections)
              }}
              displayClassName="text-xl font-semibold text-gray-800"
              className="text-xl font-semibold"
            />
          </div>
          <div className="flex items-start gap-2">
            <div className="flex-1">
              <EditableField
                value={section.content}
                onSave={(v) => {
                  const sections = [...(article.body_sections ?? [])]
                  sections[i] = { ...sections[i], content: v }
                  return save("body_sections", sections)
                }}
                multiline
                displayClassName="text-gray-700 leading-relaxed"
              />
            </div>
            <SourceChip quote={section.source_quote} />
          </div>
        </div>
      ))}

      {/* Best for / Not for */}
      <div className="grid grid-cols-2 gap-6 my-10 p-6 bg-gray-50 rounded-xl">
        <div>
          <h3 className="font-semibold text-gray-700 mb-3">Best for</h3>
          <ul className="space-y-1">
            {(article.best_for ?? []).map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-gray-600">
                <span className="text-green-500">✓</span>
                <EditableField
                  value={item.value}
                  onSave={(v) => {
                    const list = [...(article.best_for ?? [])] as ListItem[]
                    list[i] = { ...list[i], value: v }
                    return save("best_for", list)
                  }}
                  displayClassName="text-sm text-gray-600"
                />
                <SourceChip quote={item.source_quote} />
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="font-semibold text-gray-700 mb-3">Not for</h3>
          <ul className="space-y-1">
            {(article.not_for ?? []).map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-gray-600">
                <span className="text-red-400">✗</span>
                <EditableField
                  value={item.value}
                  onSave={(v) => {
                    const list = [...(article.not_for ?? [])] as ListItem[]
                    list[i] = { ...list[i], value: v }
                    return save("not_for", list)
                  }}
                  displayClassName="text-sm text-gray-600"
                />
                <SourceChip quote={item.source_quote} />
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Ethics & Safety */}
      {article.ethics_safety_notes && (
        <div className="my-8 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-yellow-800">Ethics & Safety</h3>
            <SourceChip quote={article.ethics_safety_notes_source_quote} />
          </div>
          <EditableField
            value={article.ethics_safety_notes}
            onSave={(v) => save("ethics_safety_notes", v)}
            multiline
            displayClassName="text-sm text-yellow-700"
          />
        </div>
      )}

      {/* Key facts */}
      <div className="my-10">
        <h3 className="font-semibold text-gray-700 mb-3">Key facts</h3>
        <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg">
          {(article.key_facts ?? []).map((fact, i) => (
            <div key={i} className="flex items-center px-4 py-3 bg-white first:rounded-t-lg last:rounded-b-lg">
              <EditableField
                value={fact.label}
                onSave={(v) => {
                  const facts = [...(article.key_facts ?? [])]
                  facts[i] = { ...facts[i], label: v }
                  return save("key_facts", facts)
                }}
                displayClassName="text-sm font-medium text-gray-500 w-36 shrink-0"
                className="text-sm w-36"
              />
              <EditableField
                value={fact.value}
                onSave={(v) => {
                  const facts = [...(article.key_facts ?? [])]
                  facts[i] = { ...facts[i], value: v }
                  return save("key_facts", facts)
                }}
                displayClassName="text-sm text-gray-800 flex-1"
                className="text-sm flex-1"
              />
              <SourceChip quote={fact.source_quote} />
            </div>
          ))}
        </div>
      </div>

      {/* Original notes toggle */}
      <div className="mt-12 border-t border-gray-200 pt-8">
        <button
          onClick={() => setShowOriginal((v) => !v)}
          className="text-sm text-gray-400 hover:text-gray-700 transition-colors"
        >
          {showOriginal ? "▲ Hide original notes" : "▼ View original notes"}
        </button>
        {showOriginal && (
          <pre className="mt-4 text-xs text-gray-500 bg-gray-50 rounded-lg p-4 whitespace-pre-wrap leading-relaxed font-mono">
            {article.original_text}
          </pre>
        )}
      </div>
    </article>
  )
}
