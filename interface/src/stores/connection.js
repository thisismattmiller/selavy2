import { defineStore } from "pinia";
import { socket } from "@/socket";

export const useConnectionStore = defineStore("connection", {
  state: () => ({
    isConnected: false,
  }),

  actions: {
    bindEvents() {
      socket.on("connect", (values) => {
        console.log("Connected to server",values);
        this.isConnected = true;
      });

      socket.on("disconnect", () => {
        this.isConnected = false;
      });
    },

    connect() {
      socket.connect();
    }
  },
});