import { createRouter, createWebHistory } from 'vue-router'

import ExplorerView from './views/ExplorerView.vue'
import ContactView from './views/ContactView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'explorer', component: ExplorerView },
    { path: '/home', redirect: '/' },
    { path: '/contact', name: 'contact', component: ContactView },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})
