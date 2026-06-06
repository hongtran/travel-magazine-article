"use client"
import { useState, useEffect, useRef } from "react"

interface Props {
  value: string
  onSave: (value: string) => Promise<void>
  multiline?: boolean
  placeholder?: string
  className?: string
  displayClassName?: string
}

export function EditableField({
  value,
  onSave,
  multiline = false,
  placeholder = "Click to edit",
  className = "",
  displayClassName = "",
}: Props) {
  const [editing, setEditing] = useState(false)
  const [localValue, setLocalValue] = useState(value)
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const ref = useRef<HTMLTextAreaElement & HTMLInputElement>(null)

  useEffect(() => {
    setLocalValue(value)
  }, [value])

  useEffect(() => {
    if (editing) ref.current?.focus()
  }, [editing])

  const handleSave = async () => {
    setEditing(false)
    if (localValue === value) return
    setSaveState("saving")
    try {
      await onSave(localValue)
      setSaveState("saved")
      setTimeout(() => setSaveState("idle"), 2000)
    } catch {
      setSaveState("error")
      setLocalValue(value)
      setTimeout(() => setSaveState("idle"), 3000)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") handleSave()
    if (e.key === "Escape") {
      setLocalValue(value)
      setEditing(false)
    }
  }

  const sharedInputClass = `w-full bg-amber-50 border border-amber-300 rounded px-2 py-1
    outline-none focus:ring-2 focus:ring-amber-400 resize-none ${className}`

  if (editing) {
    return multiline ? (
      <textarea
        ref={ref as React.Ref<HTMLTextAreaElement>}
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        rows={4}
        className={sharedInputClass}
      />
    ) : (
      <input
        ref={ref as React.Ref<HTMLInputElement>}
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className={sharedInputClass}
      />
    )
  }

  return (
    <span
      onClick={() => setEditing(true)}
      title={saveState === "error" ? "Save failed — click to retry" : "Click to edit"}
      className={`
        cursor-text rounded px-1 -mx-1 transition-colors block
        hover:bg-amber-50 hover:outline hover:outline-1 hover:outline-amber-200
        ${saveState === "error" ? "outline outline-1 outline-red-300 bg-red-50" : ""}
        ${displayClassName}
      `}
    >
      {localValue || <span className="text-gray-300 italic">{placeholder}</span>}
    </span>
  )
}
