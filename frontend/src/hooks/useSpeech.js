import { useCallback, useEffect, useState } from 'react'

export function useSpeech() {
  const [speaking, setSpeaking] = useState(false)

  const toggleSpeech = useCallback((text, language = 'en-US') => {
    if (!('speechSynthesis' in window)) return false
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return true
    }
    const utterance = new SpeechSynthesisUtterance(text || '')
    utterance.lang = language
    utterance.onend = () => setSpeaking(false)
    window.speechSynthesis.speak(utterance)
    setSpeaking(true)
    return true
  }, [speaking])

  useEffect(() => () => window.speechSynthesis?.cancel(), [])
  return { speaking, toggleSpeech }
}
