"use client"
import { useState } from "react"

interface Props {
  quote: string | null | undefined
}

export function SourceChip({ quote }: Props) {
  const [visible, setVisible] = useState(false)

  if (!quote) {
    return (
      <span className="inline-block ml-2 shrink-0 text-xs text-amber-600 border border-amber-300 bg-amber-50 rounded px-1.5 py-0.5">
        unverified
      </span>
    )
  }

  return (
    <span className="relative inline-block ml-2 shrink-0">
      <button
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onClick={() => setVisible((v) => !v)}
        className="text-xs text-amber-600 border border-amber-300 rounded px-1.5 py-0.5 hover:bg-amber-50 transition-colors"
      >
        source
      </button>
      {visible && (
        <span className="absolute z-10 bottom-full right-0 mb-2 w-72 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-xl leading-relaxed">
          <span className="font-semibold text-amber-300 block mb-1">From original notes:</span>
          "{quote}"
          <span className="absolute top-full right-4 border-4 border-transparent border-t-gray-900" />
        </span>
      )}
    </span>
  )
}
