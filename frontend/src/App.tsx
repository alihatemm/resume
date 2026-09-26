import { useEffect } from 'react'
import { LinkButton } from './components/Button'
import { Layout } from './components/Layout'
import { ErrorState } from './components/States'
import { href, navigate, paths, useRoute } from './router'
import { CheckpointDetail } from './screens/CheckpointDetail'
import { Dashboard } from './screens/Dashboard'
import { NewCheckpoint } from './screens/NewCheckpoint'

function App() {
  const route = useRoute()

  // "N" opens the new-checkpoint form from anywhere except while typing.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'n' || e.metaKey || e.ctrlKey || e.altKey) return
      const target = e.target
      if (target instanceof Element && target.closest('input, textarea, select, [contenteditable="true"]')) return
      e.preventDefault()
      navigate(paths.new)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <Layout route={route}>
      {route.name === 'dashboard' && <Dashboard />}
      {route.name === 'new' && <NewCheckpoint />}
      {route.name === 'detail' && <CheckpointDetail key={route.id} id={route.id} />}
      {route.name === 'not_found' && (
        <ErrorState
          title="Page not found"
          message={window.location.hash}
          action={
            <LinkButton variant="ghost" href={href(paths.dashboard)}>
              Back to checkpoints
            </LinkButton>
          }
        />
      )}
    </Layout>
  )
}

export default App
