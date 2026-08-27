async function request(url, options = {}) {
  const response = await fetch(url, options)
  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(payload?.error || `Request failed (${response.status})`)
  }
  return payload
}

function repoQuery(repos) {
  return repos.map((repo) => `repo=${encodeURIComponent(repo)}`).join('&')
}

export function fetchStatus() {
  return request('/api/status')
}

export function searchTerms(repos, query, { signal, limit = 25 } = {}) {
  const params = `${repoQuery(repos)}&q=${encodeURIComponent(query)}&limit=${limit}`
  return request(`/api/terms?${params}`, { signal })
}

export function fetchTerm(repos, id) {
  return request(`/api/terms/${encodeURIComponent(id)}?${repoQuery(repos)}`)
}

export function buildGraph({ repos, include, exclude }, { signal } = {}) {
  return request('/api/graph', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repos, include, exclude }),
    signal
  })
}
