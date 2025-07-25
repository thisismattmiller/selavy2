import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import WorkLMMReview from '../views/WorkLMMReview.vue'
import WorkNER from '../views/WorkNER.vue'



const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/llm-review/:documentId',
      name: 'llm-review',
      props: true, 
      component: WorkLMMReview,
    },
    {
      path: '/ner/:documentId',
      name: 'ner',
      props: true, 
      component: WorkNER,
    },
    
    {
      path: '/about',
      name: 'about',
      // route level code-splitting
      // this generates a separate chunk (About.[hash].js) for this route
      // which is lazy-loaded when the route is visited.
      component: () => import('../views/AboutView.vue'),
    },
  ],
})

export default router
