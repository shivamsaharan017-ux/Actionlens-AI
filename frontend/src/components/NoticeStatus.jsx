import { FileText } from 'lucide-react'

const statusLabels = {
  completed: ['Completed', 'status-complete'],
  needs_review: ['Needs review', 'status-review'],
  processing: ['Processing', 'status-processing'],
  uploaded: ['Ready to analyze', 'status-ready'],
  ready: ['Ready to analyze', 'status-ready'],
  failed: ['Failed', 'status-failed'],
}

export function StatusPill({ status }) {
  const [label, color] = statusLabels[status] || [status || 'Unknown', 'status-ready']
  return <span className={`status-pill ${color}`}><i/>{label}</span>
}

export function NoticeIcon({ status }) {
  return <div className={`notice-icon ${status === 'completed' ? 'notice-icon-green' : ''}`}><FileText size={18}/></div>
}
