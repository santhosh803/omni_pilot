import React from 'react';
import { Download, FileText, SearchCode } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
// @ts-ignore
import html2pdf from 'html2pdf.js';

interface BriefingViewerProps {
  researchOutput?: string;
  researchSources?: string[];
  researchConfidence?: number;
  activeSessionId: number | null;
}

export const BriefingViewer: React.FC<BriefingViewerProps> = ({
  researchOutput,
  researchSources,
  researchConfidence,
  activeSessionId,
}) => {
  const handleDownloadPDF = () => {
    const element = document.getElementById('briefing-pdf-content');
    if (!element) return;

    const opt = {
      margin: 0.5,
      filename: `OmniPilot_Briefing_Session_${activeSessionId || 'export'}.pdf`,
      image: { type: 'jpeg' as const, quality: 0.98 },
      html2canvas: { scale: 2, backgroundColor: '#0B0E1A' },
      jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' as const },
    };

    html2pdf().set(opt).from(element).save();
  };

  return (
    <div className="briefing-panel-container">
      <div className="briefing-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <FileText size={18} style={{ color: 'var(--accent-indigo)' }} />
          <span>Research Briefing Report</span>
        </div>
        {researchOutput && (
          <button className="download-pdf-btn" onClick={handleDownloadPDF}>
            <Download size={14} />
            <span>PDF</span>
          </button>
        )}
      </div>

      <div className="briefing-content-scroll">
        {!researchOutput ? (
          <div className="empty-state">
            <SearchCode size={48} />
            <p>No briefing output available. Trigger a research workflow.</p>
          </div>
        ) : (
          <div id="briefing-pdf-content" style={{ padding: '0.5rem' }}>
            <div
              style={{
                marginBottom: '1.5rem',
                paddingBottom: '0.75rem',
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
              }}
            >
              {researchConfidence !== undefined && (
                <span>
                  Confidence:{' '}
                  <strong style={{ color: 'var(--success)' }}>
                    {(researchConfidence * 100).toFixed(1)}%
                  </strong>
                </span>
              )}
              {researchSources && (
                <span>
                  Sources: <strong>{researchSources.length}</strong>
                </span>
              )}
            </div>

            <div className="briefing-markdown">
              <ReactMarkdown>{researchOutput}</ReactMarkdown>
            </div>

            {researchSources && researchSources.length > 0 && (
              <div
                style={{
                  marginTop: '2rem',
                  paddingTop: '1rem',
                  borderTop: '1px dashed var(--border-subtle)',
                }}
              >
                <h4
                  style={{
                    color: 'white',
                    marginBottom: '0.5rem',
                    fontSize: '0.9rem',
                  }}
                >
                  Sources Referenced:
                </h4>
                <ul
                  style={{
                    fontSize: '0.8rem',
                    color: 'var(--text-secondary)',
                    marginLeft: '1.25rem',
                  }}
                >
                  {researchSources.map((source, i) => (
                    <li key={i} style={{ marginBottom: '0.25rem' }}>
                      <a
                        href={source}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--accent-indigo)', textDecoration: 'none' }}
                      >
                        {source}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
