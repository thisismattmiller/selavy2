import { defineStore } from "pinia";
import { socket } from "@/socket";

export const useConnectionStore = defineStore("connection", {
  state: () => ({
    isConnected: false,
  }),

  actions: {
    bindEvents() {
      socket.on("connect", () => {
        this.isConnected = true;
        console.log("Connected to the server");
      });

      socket.on("disconnect", () => {
        this.isConnected = false;
        console.log(" disconnected from the server");
      });
    },

    connect() {
      socket.connect();
    }
  },
});